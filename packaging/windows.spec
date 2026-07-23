# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH).parent
frontend = root / "frontend" / "dist"
migrations = root / "backend" / "app" / "db" / "migrations"

analysis = Analysis(
    [str(root / "backend" / "app" / "launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[
        (str(frontend), "frontend/dist"),
        (str(migrations), "backend/app/db/migrations"),
        (str(root / "LICENSE"), "."),
        (str(root / "PRIVACY.md"), "."),
    ],
    hiddenimports=[
        "sqlalchemy.dialects.sqlite.pysqlite",
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "ruff"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="AIErrorReviewWorkbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="AIErrorReviewWorkbench",
)
