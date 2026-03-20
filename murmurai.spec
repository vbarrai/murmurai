import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

datas = collect_data_files("faster_whisper") + collect_data_files("ctranslate2")
binaries = collect_dynamic_libs("ctranslate2") + collect_dynamic_libs("soundfile")

a = Analysis(
    ["murmurai/app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        "murmurai",
        "murmurai.app",
        "murmurai.recorder",
        "murmurai.transcriber",
        "murmurai.paster",
        "rumps",
        "pynput",
        "pynput.keyboard",
        "pynput.keyboard._darwin",
        "sounddevice",
        "soundfile",
        "numpy",
        "faster_whisper",
        "ctranslate2",
        "huggingface_hub",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="murmurai",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="murmurai",
)

app = BUNDLE(
    coll,
    name="murmurai.app",
    icon=None,
    bundle_identifier="com.vbarrai.murmurai",
    info_plist={
        "CFBundleName": "murmurai",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "LSUIElement": True,
        "NSMicrophoneUsageDescription": "murmurai needs microphone access to record speech for transcription.",
    },
)
