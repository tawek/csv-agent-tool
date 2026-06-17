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

The remote build environment (venv + source checkout) is set up once. Every build must still refresh Python requirements on the remote machine so new project dependencies are bundled into the Windows artifact.

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

**Step 2 — Install Baseline Build Tooling on Remote**

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "C:\Users\gfl\build-env\Scripts\python.exe -m pip install pyinstaller"'
```

This installs only the baseline build tool. Project runtime dependencies are refreshed from `pyproject.toml` during every build.

**Step 3 — Clone Source on Remote**

```bash
ssh gfl@192.168.1.13 'cd /home/gfl && git clone git@github.com:tawek/csv-agent-tool.git csv-agent-tool'
```

---

## Standard Build (Steps 4–8)

### Clean Temp Directory

Always use a unique, timestamped temp directory for each build to avoid stale/corrupted data from previous builds:

```bash
BUILD_DIR="/tmp/product-description-tool-$(date +%Y%m%d-%H%M%S)"
```

**Step 4 — Check for Running Build**

Before starting, ensure no previous build is still running. The build uses a file-based lock (`/home/gfl/.build.lock`) that `mkdir` creates atomically:

```bash
ssh gfl@192.168.1.13 \
  'if ! mkdir /home/gfl/.build.lock 2>/dev/null; then echo "Build already running, waiting..."; while ! mkdir /home/gfl/.build.lock 2>/dev/null; do sleep 5; done; fi'
```

This blocks until the previous build releases the lock (removes the directory).

**Step 5 — Sync Fresh Source via Archive**

Always push the latest local source to the remote to avoid stale builds. Use `git archive` piped over SSH — this pushes only the current HEAD without requiring git on the remote:

```bash
git archive --format=tar HEAD | ssh gfl@192.168.1.13 'tar -xC /home/gfl/csv-agent-tool --strip-components=0'
```

**Step 6 — Refresh Remote Python Requirements**

Always reinstall the current project dependencies on the remote builder before packaging. Do not rely on a one-time remote `pip install` list because new dependencies will otherwise be missing from the packaged app.

```bash
uv run python -c "import tomllib, pathlib; data = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print('\n'.join(data['project']['dependencies'] + data['project']['optional-dependencies']['dev']))" \
  | ssh gfl@192.168.1.13 'xargs -r "/cygdrive/c/Users/gfl/build-env/Scripts/python.exe" -m pip install'
```

This keeps the remote build environment aligned with the current `pyproject.toml` dependency set, including packaged runtime dependencies such as MarkItDown and its conversion extras.

**Step 7 — Build with PyInstaller**

Run the build; it will release the lock when finished (success or failure):

```bash
ssh gfl@192.168.1.13 \
  'cmd.exe /c "set PYTHONPATH=C:\cygwin64\home\gfl\csv-agent-tool\src && cd /d C:\cygwin64\home\gfl\csv-agent-tool && C:\Users\gfl\build-env\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\product_description_tool.spec" && rmdir /home/gfl/.build.lock'
```

Use `&&` to ensure the lock is only removed on success. If the build fails, the lock persists and you can manually remove it with `ssh gfl@192.168.1.13 'rmdir /home/gfl/.build.lock'`.

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

**Step 8 — Add install.bat**

Copy the installation script into the dist directory:

```bash
cp packaging/install.bat /home/gfl/csv-agent-tool/dist/product-description-tool/
```

The `install.bat` script copies the application from wherever it was downloaded (e.g., Google Drive folder) to `C:\apps\product-description-tool\`.

---

**Step 9 — Retrieve the Build (Tar Stream)**

Do **not** use `scp` — it is extremely slow for 500+ MB of small files. Use tar streaming instead:

```bash
BUILD_DIR="/tmp/product-description-tool-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BUILD_DIR"
ssh gfl@192.168.1.13 'cd /home/gfl/csv-agent-tool/dist && tar -czf - product-description-tool' | tar -C "$BUILD_DIR" -xzf -
```

The output includes:
- `product-description-tool.exe` (~7 MB, the entry point)
- `_internal/` (~110-130 MB with spec filters, all Qt DLLs, Python extensions, bundled packages)

**Verify size before upload:**

```bash
du -sh "$BUILD_DIR/product-description-tool/"
# Should be ~120 MB total. If ~550 MB+, the spec excludes were not applied — do NOT upload.
```

**Step 10 — Upload to Google Drive**

Check rclone token expiry first. If expired, re-authenticate:

```bash
rclone ls GoogleDrive:WFirma/product-description-tool/ > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Token expired. Re-authorizing..."
  rclone authorize "drive" "<client_id> <client_secret>"
fi

rclone copy "$BUILD_DIR/product-description-tool/" GoogleDrive:WFirma/product-description-tool/ \
  --transfers=4 --checkers=8
```

Verify completion:

```bash
rclone size GoogleDrive:WFirma/product-description-tool/
# Should report ~170-200 objects, ~120-140 MiB
```

---

## Full One-Liner (Complete Build)

```bash
# 0. Setup clean build directory
BUILD_DIR="/tmp/product-description-tool-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BUILD_DIR"

# 1. Check for running build and wait
ssh gfl@192.168.1.13 \
  'if ! mkdir /home/gfl/.build.lock 2>/dev/null; then echo "Build already running, waiting..."; while ! mkdir /home/gfl/.build.lock 2>/dev/null; do sleep 5; done; fi'

# 2. Sync fresh source
git archive --format=tar HEAD | ssh gfl@192.168.1.13 'tar -xC /home/gfl/csv-agent-tool --strip-components=0'

# 3. Refresh remote Python requirements from pyproject.toml
uv run python -c "import tomllib, pathlib; data = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print('\n'.join(data['project']['dependencies'] + data['project']['optional-dependencies']['dev']))" \
  | ssh gfl@192.168.1.13 'xargs -r "/cygdrive/c/Users/gfl/build-env/Scripts/python.exe" -m pip install'

# 4. Build (lock is removed on success)
ssh gfl@192.168.1.13 \
  'cmd.exe /c "set PYTHONPATH=C:\cygwin64\home\gfl\csv-agent-tool\src && cd /d C:\cygwin64\home\gfl\csv-agent-tool && C:\Users\gfl\build-env\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging\product_description_tool.spec" && rmdir /home/gfl/.build.lock'

# 5. Add install.bat to dist
scp packaging/install.bat gfl@192.168.1.13:/home/gfl/csv-agent-tool/dist/product-description-tool/

# 6. Retrieve via tar stream
ssh gfl@192.168.1.13 'cd /home/gfl/csv-agent-tool/dist && tar -czf - product-description-tool' | tar -C "$BUILD_DIR" -xzf -

# 7. Verify size before upload
du -sh "$BUILD_DIR/product-description-tool/"
# If >200 MB, abort — spec excludes were not applied correctly

# 8. Check token and upload
rclone ls GoogleDrive:WFirma/product-description-tool/ > /dev/null 2>&1 || \
  rclone authorize "drive" "<client_id> <client_secret>"
rclone copy "$BUILD_DIR/product-description-tool/" GoogleDrive:WFirma/product-description-tool/ \
  --transfers=4 --checkers=8

# 9. Verify size
rclone size GoogleDrive:WFirma/product-description-tool/
# Should report ~170-200 objects, ~120-140 MiB

# 10. Clean up temp directory (only on success — leave on failure for post-mortem)
rclone size GoogleDrive:WFirma/product-description-tool/ >/dev/null 2>&1 && rm -rf "$BUILD_DIR"
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

### rclone uses content hashing, not mtime

rclone determines whether to re-upload files by comparing content hashes, **not modification times**. Touching a file (changing only its mtime) does **not** trigger a re-upload — rclone only updates the destination's mtime to match the source.

This means:
- Re-running rclone after a build is safe; unchanged files are skipped entirely (0 bytes transferred if nothing changed).
- The mtime sync is cosmetic — it doesn't affect which files get uploaded.
- Use `--log-level=INFO --log-file=/tmp/rclone-upload.log` to verify what was actually transferred. The log will say "There was nothing to transfer" when all files are already up to date.

### `scp` is too slow for the build directory

`scp -r` on a 500+ MB directory with thousands of small files can take 10+ minutes. Use the tar streaming method in Step 6 instead.
