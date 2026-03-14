# Cancellation of Long-Running Operations

This document describes the patterns and pitfalls for implementing cancellable background
operations in a PySide6 application, derived from a real bug that caused the main window
to become permanently unresponsive after the user cancelled a generation run.

---

## The Architecture

Long-running work (e.g. calling an LLM API) runs on a `QThread`. The main thread owns
the UI. Communication goes through Qt signals. The overall shape looks like this:

```
MainWindow
  │
  ├─ _start_worker()
  │     creates GenerationWorker + QThread
  │     connects signals
  │     thread.start()
  │
  │   [worker runs in QThread]
  │     worker.run()
  │       → provider.generate()   ← blocks on HTTP stream
  │       → emits: chunk_generated, row_generated, progress
  │       → emits: completed | cancelled | failed
  │
  ├─ _cancel_processing()         ← called from UI (Cancel button)
  │     sets _cancel_requested flag
  │     closes the activity dialog
  │     calls worker.cancel()
  │         → sets threading.Event
  │         → calls provider.cancel()
  │             → closes the httpx.Client  ← unblocks the stream
  │
  └─ _clear_worker_state()        ← connected to thread.finished
        clears _worker_thread
        re-enables UI
```

---

## Rule 1 — Interrupt the blocking I/O, don't just set a flag

A `threading.Event` (or a boolean flag) only helps at **check points** — places in the
loop where you test `should_cancel()`. If the thread is blocked inside a syscall waiting
for the next TCP packet, no flag will ever be checked.

**Wrong:**
```python
# cancel() only sets a flag — thread stays blocked in iter_lines() until the
# server closes the connection or the full response arrives.
def cancel(self) -> None:
    self._cancel_requested.set()
```

**Right:**
```python
# cancel() sets the flag AND forcefully closes the underlying TCP connection.
def cancel(self) -> None:
    self._cancel_requested.set()
    with self._http_client_lock:
        client = self._http_client
    if client is not None:
        client.close()          # raises in the worker thread, unblocking iter_lines()
```

The worker's `generate()` method must catch the resulting `httpx` exception and convert
it to `GenerationCancelled` when the cancel flag is set:

```python
except httpx.HTTPError as exc:
    if should_cancel is not None and should_cancel():
        raise GenerationCancelled("Generation cancelled.") from exc
    raise
```

---

## Rule 2 — Store the cancellable handle *before* making the blocking call

There is a race between `cancel()` (called from the main thread) and the worker setting
up its connection. If `cancel()` arrives before the handle is stored, it is a no-op and
the thread hangs.

**Wrong:**
```python
with httpx.Client() as client:
    with client.stream(...) as response:
        self._active_close = response.close   # too late — cancel() may have already fired
        for line in response.iter_lines():
            ...
```

**Right:**
```python
http_client = httpx.Client()
with self._lock:
    self._http_client = http_client          # stored BEFORE the network call
try:
    with http_client.stream(...) as response:
        for line in response.iter_lines():
            ...
finally:
    with self._lock:
        self._http_client = None
    http_client.close()
```

Now `cancel()` can always find and close the client, regardless of when it is called.

---

## Rule 3 — Never call `setModal(False)` on a visible QDialog

This was the root cause of the UI freeze.

On macOS, showing a `QDialog` with `setModal(True)` and `show()` starts a **native Cocoa
modal session** that blocks user input to the parent window. That session is ended only
when the dialog is properly **closed** (hidden) through the Cocoa path.

Calling `setModal(False)` on a *still-visible* dialog only flips a Qt-internal flag. It
does **not** end the Cocoa session. The parent window stays input-blocked forever, even
after the dialog is subsequently closed.

**Wrong:**
```python
def request_cancel(self) -> None:
    self.setModal(False)       # ← corrupts the Cocoa modal stack on macOS
    self.cancel_requested.emit()
    # _cancel_processing() → close_activity() → self.close()
    # The close() does NOT fix the already-broken modal session.
```

**Right:**
```python
def request_cancel(self) -> None:
    # Do NOT touch modality — just update UI state and emit the signal.
    # The dialog will be closed by the owner (MainWindow), which properly
    # ends the native modal session.
    self.cancel_button.setEnabled(False)
    self.cancel_button.setText("Cancelling...")
    self.cancel_requested.emit()
```

The general rule: **change `windowModality` only before `show()` or after `hide()`**.

---

## Rule 4 — Re-enable the UI in one place, after the thread is gone

`_busy` and `_worker_thread` are two separate guards. Interactive controls (filter,
settings, prompts) are gated on `not _busy`. Processing controls (Process, Preview) are
gated on `not _busy AND _worker_thread is None`.

When the user cancels:

- `_busy` is set to `False` immediately — non-processing controls become usable.
- `_worker_thread` is cleared only in `_clear_worker_state`, connected to
  `thread.finished` — processing controls are re-enabled only once the thread is
  actually done.

`_clear_worker_state` must call `_set_busy(False)` **after** setting
`_worker_thread = None`, so that `_update_interactive_state` evaluates
`processing_controls_enabled = not False and None is None = True`.

```python
def _clear_worker_state(self) -> None:
    self._worker = None
    self._worker_thread = None       # cleared first
    self._set_busy(False)            # now re-enables everything
```

If `_set_busy(False)` were called while `_worker_thread` is still set (e.g. from a
signal handler that fires before `thread.finished`), the process buttons would stay
disabled until the next call with `_worker_thread = None`.

---

## Summary of Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| Cancel only sets a flag, no I/O interrupt | Thread hangs; UI stuck in "cancelling" forever | Close the `httpx.Client` from `cancel()` |
| Cancellable handle stored after connection open | Race: cancel fires before handle is set; no-op | Store handle before the blocking call |
| `setModal(False)` called on visible dialog | Parent window frozen after dialog closes (macOS) | Never change modality on a visible dialog |
| UI re-enabled while `_worker_thread` still set | Process buttons stay disabled after cancel | Clear `_worker_thread` before calling `_set_busy(False)` |

