# Windows Build Procedure

Build a Windows executable for Product Description Tool using a remote Windows machine accessible via SSH.

## Remote Machine

- **Host:** `192.168.1.13`
- **User:** `gfl`
- **Shell:** Cygwin64 (SSH)
- **Python:** `C:\Users\gfl\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe` (managed by uv)
- **Git:** Available at `C:\cygwin64\bin\git.exe`

---

## Prerequisites

The remote build environment (venv + dependencies) is set up once. Subsequent builds only need steps 4–7.

### One-Time Setup (Steps 1–3)

**Step 1 — Create a Virtual Environment on Remote**

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\AppData\Roaming\uv\python\cpython-3.12.13-windows-x86_64-none\python.exe -m venv C:\Users\gfl\build-env"'
```

Upgrade pip:

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install --upgrade pip"'
```

**Step 2 — Install Dependencies on Remote**

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install pyinstaller httpx openai platformdirs PySide6"'
```

This downloads PySide6 (~250 MB). Expect 2–5 minutes.

**Step 3 — Clone Source on Remote**

```bash
ssh gfl@192.168.1.13 'cd /home/gfl && git clone git@github.com:tawek/csv-agent-tool.git csv-agent-tool'
```

---

## Standard Build (Steps 4–7)

**Step 4 — Sync Fresh Source via Archive**

Always push the latest local source to the remote to avoid stale builds. Use `git archive` piped over SSH — this pushes only the current HEAD without requiring git on the remote:

```bash
git archive --format=tar HEAD | ssh gfl@192.168.1.13 'tar -xC /home/gfl/csv-agent-tool --strip-components=0'
```

**Step 5 — Build with PyInstaller**

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "set PYTHONPATH=C:\cygwin64\home\gfl\csv-agent-tool\src && cd /d C:\cygwin64\home\gfl\csv-agent-tool && C:\Users\gfl\build-env\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\product_description_tool.spec"'
```

**Key notes:**
- `PYTHONPATH` must point to the `src/` directory inside the project root.
- Use `cd /d` (not just `cd`) in cmd.exe to handle path changes across filesystem boundaries.
- The project lives under `C:\cygwin64\home\gfl\...` on the Windows side (visible via `cmd.exe`), NOT under `C:\Users\gfl\...`.
- Output directory: `/home/gfl/csv-agent-tool/dist/product-description-tool/`.

Build takes ~2 minutes.

**Step 6 — Add install.bat**

Copy the installation script into the dist directory:

```bash
cp packaging/install.bat /home/gfl/csv-agent-tool/dist/product-description-tool/
```

The `install.bat` script copies the application from wherever it was downloaded (e.g., Google Drive folder) to `C:\apps\product-description-tool\`.

---

**Step 7 — Retrieve the Build (Tar Stream)**

Do **not** use `scp` — it is extremely slow for 500+ MB of small files. Use tar streaming instead:

```bash
ssh gfl@192.168.1.13 'cd /home/gfl/csv-agent-tool/dist && tar -czf - product-description-tool' | tar -C /tmp -xzf -
```

The output includes:
- `product-description-tool.exe` (~7 MB, the entry point)
- `_internal/` (~559 MB, all Qt DLLs, Python extensions, bundled packages)

**You must ship the entire directory.** The exe won't run without the `_internal` folder.

**Step 7 — Upload to Google Drive**

Check rclone token expiry first. If expired, re-authenticate:

```bash
rclone ls GoogleDrive:WFirma/product-description-tool/ > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Token expired. Re-authorizing..."
  rclone authorize "drive" "<client_id> <client_secret>"
fi

rclone copy /tmp/product-description-tool/ GoogleDrive:WFirma/product-description-tool/ \
  --transfers=4 --checkers=8
```

Verify completion:

```bash
rclone size GoogleDrive:WFirma/product-description-tool/
# Should report ~2965 objects, ~566 MiB
```

---

## Full One-Liner (Complete Build)

```bash
# 1. Sync fresh source
git archive --format=tar HEAD | ssh gfl@192.168.1.13 'tar -xC /home/gfl/csv-agent-tool'

# 2. Build
ssh gfl@192.168.1.13 \
  'cmd.exe /c "set PYTHONPATH=C:\cygwin64\home\gfl\csv-agent-tool\src && cd /d C:\cygwin64\home\gfl\csv-agent-tool && C:\Users\gfl\build-env\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\product_description_tool.spec"'

# 3. Add install.bat to dist
scp packaging/install.bat gfl@192.168.1.13:/home/gfl/csv-agent-tool/dist/product-description-tool/

# 4. Retrieve via tar stream
ssh gfl@192.168.1.13 'cd /home/gfl/csv-agent-tool/dist && tar -czf - product-description-tool' | tar -C /tmp -xzf -

# 5. Check token and upload
rclone ls GoogleDrive:WFirma/product-description-tool/ > /dev/null 2>&1 || \
  rclone authorize "drive" "<client_id> <client_secret>"
rclone copy /tmp/product-description-tool/ GoogleDrive:WFirma/product-description-tool/ \
  --transfers=4 --checkers=8
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

### rclone token expired

If `rclone ls GoogleDrive:...` fails with "couldn't fetch token: invalid_grant", re-authorize:

```bash
rclone authorize "drive" "<client_id> <client_secret>"
```

**Never use `rclone config` interactively** — it corrupts the config file if interrupted. Always use `rclone authorize` which writes to the same token field non-interactively.

### `scp` is too slow for the build directory

`scp -r` on a 500+ MB directory with thousands of small files can take 10+ minutes. Use the tar streaming method in Step 6 instead.
