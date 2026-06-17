# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import re

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules("markitdown")
datas = collect_data_files("markitdown") + collect_data_files("magika")
excludes = [
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtMultimedia",
    "PySide6.QtLocation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DExtras",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtVirtualKeyboard",
    "PySide6.QtWaylandClient",
    "PySide6.QtWaylandCompositor",
    "PySide6.QtWebSockets",
    "PySide6.QtWebView",
]
project_root = Path(SPEC).resolve().parent.parent

block_cipher = None

a = Analysis(
    [str(project_root / "src/product_description_tool/__main__.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter out QML, translations, and unused Qt resources
qml_pattern = re.compile(r'[/\\]qml[/\\]')
translations_pattern = re.compile(r'[/\\]translations[/\\]')
resources_pattern = re.compile(r'[/\\]resources[/\\]')
unnecessary_plugins = re.compile(r'[/\\](?:position|wayland-shell-integration|qmltooling)[/\\]')

def filter_items(items, pattern):
    result = []
    for item in items:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            dst = item[1]
        else:
            dst = item
        if not pattern.search(str(dst)):
            result.append(item)
    return result

a.datas = filter_items(a.datas, qml_pattern)
a.datas = filter_items(a.datas, translations_pattern)
a.datas = filter_items(a.datas, resources_pattern)
a.datas = filter_items(a.datas, unnecessary_plugins)
a.binaries = filter_items(a.binaries, qml_pattern)
a.binaries = filter_items(a.binaries, translations_pattern)
a.binaries = filter_items(a.binaries, resources_pattern)
a.binaries = filter_items(a.binaries, unnecessary_plugins)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="product-description-tool",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="product-description-tool",
)
