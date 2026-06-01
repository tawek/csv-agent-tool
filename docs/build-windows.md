# Windows Build Procedure

Build a Windows executable for Product Description Tool using a remote Windows machine accessible via SSH.

## Remote Machine

- **Host:** `192.168.1.13`
- **User:** `gfl`
- **Shell:** Cygwin64 (SSH)
- **Python:** `C:\Users\gfl\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe` (managed by uv)
- **Git:** Available at `C:\cygwin64\bin\git.exe`

---

## Step 1 — Create a Virtual Environment on Remote

The system Python installed by uv is externally managed. Use `venv` to get an isolated environment with pip and PyInstaller.

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe -m venv C:\Users\gfl\build-env"'
```

Upgrade pip in the venv:

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install --upgrade pip"'
```

---

## Step 2 — Install Dependencies on Remote

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install pyinstaller httpx openai platformdirs PySide6"'
```

This downloads PySide6 (~250 MB combined addons) and all transitive dependencies. Expect 2–5 minutes depending on network speed.

---

## Step 3 — Get the Source Code on Remote

**Option A — Clone from GitHub** (requires SSH keys or HTTPS credentials configured on the remote):

```bash
ssh gfl@192.168.1.13 'cd /home/gfl && git clone git@github.com:tawek/csv-agent-tool.git csv-agent-tool'
```

**Option B — Archive from local machine** (no git credentials needed):

```bash
cd /home/tawek/projects/csv-agent-tool   # or wherever the repo lives locally
ssh gfl@192.168.1.13 'mkdir -p /home/gfl/csv-agent-tool'
git archive --format=tar HEAD | ssh gfl@192.168.1.13 'tar -xC /home/gfl/csv-agent-tool'
```

---

## Step 4 — Build with PyInstaller

Use the native Windows Python (not the Cygwin path), set `PYTHONPATH`, and run from the project root:

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "set PYTHONPATH=C:\cygwin64\home\gfl\csv-agent-tool\src && cd /d C:\cygwin64\home\gfl\csv-agent-tool && C:\Users\gfl\build-env\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\product_description_tool.spec"'
```

**Key notes:**
- `PYTHONPATH` must point to the `src/` directory inside the project root.
- Use `cd /d` (not just `cd`) in cmd.exe to handle path changes across filesystem boundaries.
- The project lives under `C:\cygwin64\home\gfl\...` on the Windows side (visible via `cmd.exe`), NOT under `C:\Users\gfl\...`.
- Output directory: `/home/gfl/csv-agent-tool/dist/product-description-tool/` (accessible in Cygwin as `/home/gfl/csv-agent-tool/dist/`).

Build takes ~2 minutes.

---

## Step 5 — Retrieve the Build

Copy the entire dist folder back locally:

```bash
scp -r gfl@192.168.1.13:/home/gfl/csv-agent-tool/dist/product-description-tool /tmp/product-description-tool-windows
```

The output includes:
- `product-description-tool.exe` (~7 MB, the entry point)
- `_internal/` (~559 MB, all Qt DLLs, Python extensions, bundled packages)

**You must ship the entire directory.** The exe won't run without the `_internal` folder.

---

## Step 6 — Upload to Google Drive

```bash
rclone copy /tmp/product-description-tool-windows/ GoogleDrive:WFirma/product-description-tool/ \
  --transfers=4 --checkers=8
```

Silent mode (no progress output). For progress logging:

```bash
rclone copy /tmp/product-description-tool-windows/ GoogleDrive:WFirma/product-description-tool/ \
  --transfers=4 --checkers=8 >> /tmp/rclone-upload.log 2>&1 &
```

Verify completion:

```bash
rclone size GoogleDrive:WFirma/product-description-tool/
# Should report ~2965 objects, ~566 MiB
```

---

## Troubleshooting

### `cmd.exe /c` fails with "System nie może określić..." (Polish for "cannot find path")

Cygwin paths (`/home/gfl/...`) are not valid in cmd.exe. The Windows-side path for a Cygwin home is `C:\cygwin64\home\gfl\...`.

### `cd /d` is required

Without the `/d` flag, `cd` in cmd.exe does not change drives or cross filesystem boundaries. Always use `cd /d` when changing to a Cygwin-mounted path.

### `tasklist` returns "Access denied"

The `tasklist` command requires administrator privileges. You cannot verify running processes from SSH without elevation.

### GUI app won't show a window

The built exe uses `console=False` in the PyInstaller spec. If you try to run it remotely via SSH, there is no interactive desktop session, so the app runs but displays nothing visible.

### `uv` is not on PATH

The remote machine does not have `uv` in its PATH. All Python operations must use the full path to the executable under `C:\Users\gfl\AppData\Roaming\uv\python\...`.

### `hiddenimports` hook warning about `tzdata`

PyInstaller may log: `WARNING: Hidden import "tzdata" not found!`. This is harmless — PySide6 uses zoneinfo data from the standard library on Python 3.9+. The build succeeds regardless.

---

## Full One-Liner (Everything in Sequence)

For convenience, here is the complete sequence to build from scratch:

```bash
# 1. Create venv
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe -m venv C:\Users\gfl\build-env"'

# 2. Upgrade pip
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install --upgrade pip"'

# 3. Install deps
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install pyinstaller httpx openai platformdirs PySide6"'

# 4. Clone repo (if needed)
ssh gfl@192.168.1.13 'cd /home/gfl && git clone git@github.com:tawek/csv-agent-tool.git csv-agent-tool'

# 5. Build
ssh gfl@192.168.1.13 \
  'cmd.exe /c "set PYTHONPATH=C:\cygwin64\home\gfl\csv-agent-tool\src && cd /d C:\cygwin64\home\gfl\csv-agent-tool && C:\Users\gfl\build-env\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\product_description_tool.spec"'

# 6. Copy back
scp -r gfl@192.168.1.13:/home/gfl/csv-agent-tool/dist/product-description-tool /tmp/product-description-tool-windows
```
