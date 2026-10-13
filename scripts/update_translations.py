#!/usr/bin/env python3
"""Synchronizes and compiles Qt translation catalogs (.ts and .qm).

Runs pyside6-lupdate across application source files to extract new strings,
then runs pyside6-lrelease to compile binary .qm files.
"""

import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALIZATION_DIR = os.path.join(PROJECT_ROOT, "application", "localization")

TS_FILES = [
    os.path.join(LOCALIZATION_DIR, f)
    for f in [
        "app_de-DE.ts",
        "app_ja-JP.ts",
        "app_ko-KR.ts",
        "app_ru-RU.ts",
        "app_vi-VN.ts",
        "app_zh-TW.ts",
    ]
]

SOURCE_PATHS = [
    os.path.join(PROJECT_ROOT, "application", "main.py"),
    os.path.join(PROJECT_ROOT, "application", "ui"),
    os.path.join(PROJECT_ROOT, "application", "core"),
    os.path.join(PROJECT_ROOT, "application", "tools"),
]


def update_ts():
    print("--> Extracting translatable strings with pyside6-lupdate...")
    cmd = [
        "pyside6-lupdate",
        *SOURCE_PATHS,
        "-ts",
        *TS_FILES,
    ]
    try:
        subprocess.run(cmd, check=True)
        print("    Updated .ts translation files.")
    except Exception as e:
        print(f"    Warning: pyside6-lupdate failed: {e}")


def compile_qm():
    print("--> Compiling binary .qm catalogs with pyside6-lrelease...")
    cmd = [
        "pyside6-lrelease",
        "-compress",
        *TS_FILES,
    ]
    try:
        subprocess.run(cmd, check=True)
        print("    Compiled .qm catalogs successfully.")
    except Exception as e:
        print(f"    ERROR: pyside6-lrelease failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    update_ts()
    compile_qm()
    print("--> Translation synchronization complete!")
