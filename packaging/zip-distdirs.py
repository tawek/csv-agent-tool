"""Post-PyInstaller build script.

Archives directories with many small files (e.g., tzdata zoneinfo,
pdfminer cmap) into single zip files, and bundles a standalone 32-bit
unzip.exe for extraction at install time.

Run after PyInstaller completes, from the project root.

Usage:
    uv run python packaging/zip-distdirs.py
"""

import shutil
import sys
from pathlib import Path

DIST_DIR = Path("dist/product-description-tool/_internal")
PACKAGING_DIR = Path("packaging")

TARGETS = [
    "tzdata",
    "pdfminer/cmap",
]


def main() -> None:
    dist = DIST_DIR.resolve()
    if not dist.is_dir():
        sys.exit(f"Dist _internal directory not found: {dist}")

    print(f"Post-processing {dist}...")
    for rel_path in TARGETS:
        src = dist / rel_path
        if not src.is_dir():
            print(f"  SKIP (not found): {rel_path}/")
            continue

        orig_files = sum(1 for _ in src.rglob("*"))
        zip_name = rel_path.replace("/", "-") + ".zip"
        dst = dist / zip_name
        print(f"  Archiving {rel_path}/ ({orig_files} files) -> {zip_name} ...")
        shutil.make_archive(str(dst.with_suffix("")), "zip", src)
        shutil.rmtree(src)
        print(f"    Replaced {orig_files} files with {zip_name}")

    unzip_src = PACKAGING_DIR / "unzip.exe"
    unzip_dst = dist / "unzip.exe"
    if unzip_src.is_file() and not unzip_dst.is_file():
        shutil.copy2(unzip_src, unzip_dst)
        print(f"  Copied unzip.exe ({unzip_src.stat().st_size // 1024} KiB)")

    print("Done.")


if __name__ == "__main__":
    main()
