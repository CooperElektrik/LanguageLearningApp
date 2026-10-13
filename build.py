#!/usr/bin/env python3
"""Build and packaging script for LanguageLearningApp.

Compiles Qt translation catalogs and creates a standalone PyInstaller
executable bundle for distribution.

Usage:
    python build.py [--onedir | --onefile] [--clean] [--skip-translations]
"""

import argparse
import os
import shutil
import subprocess
import sys


def run_command(cmd: list[str], description: str) -> bool:
    """Runs a subprocess command and streams its output."""
    print(f"\n--> {description}...")
    print(f"    Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {description} failed with return code {e.returncode}.")
        return False
    except FileNotFoundError:
        print(f"ERROR: Command '{cmd[0]}' not found. Ensure required tools are installed.")
        return False


def compile_translations(project_root: str) -> bool:
    """Compiles all .ts files in application/localization using pyside6-lrelease."""
    loc_dir = os.path.join(project_root, "application", "localization")
    if not os.path.isdir(loc_dir):
        print("Localization directory not found, skipping translation compilation.")
        return True

    ts_files = [os.path.join(loc_dir, f) for f in os.listdir(loc_dir) if f.endswith(".ts")]

    if not ts_files:
        print("No .ts files found to compile.")
        return True

    lrelease_cmd = [
        sys.executable,
        "-m",
        "PySide6.scripts.pyside_tool",
        "lrelease",
        "-compress",
        *ts_files,
    ]
    # Fallback to direct pyside6-lrelease executable if tool invocation fails
    success = run_command(lrelease_cmd, "Compiling Qt translation catalogs")
    if not success:
        direct_cmd = ["pyside6-lrelease", "-compress", *ts_files]
        success = run_command(direct_cmd, "Retrying with direct pyside6-lrelease")

    return success


def build_executable(
    project_root: str,
    onefile: bool = False,
    clean: bool = False,
    app_name: str = "LanguageLearningApp",
) -> bool:
    """Builds the application using PyInstaller."""
    main_script = os.path.join(project_root, "application", "main.py")
    icon_path = os.path.join(project_root, "application", "assets", "icons", "logo.png")

    # Data directories to bundle (source:destination)
    sep = ";" if sys.platform.startswith("win") else ":"
    data_bundles = [
        (os.path.join(project_root, "courses"), "courses"),
        (os.path.join(project_root, "application", "assets"), "assets"),
        (os.path.join(project_root, "application", "localization"), "localization"),
        (os.path.join(project_root, "application", "tools", "styles"), "tools/styles"),
    ]

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        app_name,
        "--windowed",
        "--noconfirm",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if clean:
        cmd.append("--clean")

    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])

    for src, dst in data_bundles:
        if os.path.exists(src):
            cmd.extend(["--add-data", f"{src}{sep}{dst}"])

    # Collect binary packages and dynamic modules
    cmd.extend(
        [
            "--collect-all",
            "vosk",
            "--collect-all",
            "av",
            "--collect-submodules",
            "sounddevice",
            "--collect-submodules",
            "soundfile",
            "--collect-submodules",
            "yaml",
            "--paths",
            os.path.join(project_root, "application"),
            "--distpath",
            os.path.join(project_root, "dist"),
            "--workpath",
            os.path.join(project_root, "build"),
            main_script,
        ]
    )

    return run_command(cmd, f"Building {app_name} executable")


def main():
    parser = argparse.ArgumentParser(description="Build LanguageLearningApp executable.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--onedir",
        action="store_true",
        default=True,
        help="Build a directory containing the executable and shared libraries (default).",
    )
    group.add_argument(
        "--onefile",
        action="store_true",
        help="Build a single self-contained executable.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove build and dist folders before building.",
    )
    parser.add_argument(
        "--skip-translations",
        action="store_true",
        help="Skip compiling .ts translation files to .qm.",
    )

    args = parser.parse_args()
    project_root = os.path.dirname(os.path.abspath(__file__))

    print("=" * 60)
    print(" LanguageLearningApp Build & Packaging")
    print(f" Platform : {sys.platform} | Python: {sys.version.split()[0]}")
    print(f" Target   : {'Onefile' if args.onefile else 'Onedir'}")
    print("=" * 60)

    if args.clean:
        for folder in ("build", "dist"):
            path = os.path.join(project_root, folder)
            if os.path.exists(path):
                print(f"Cleaning {folder}/ ...")
                shutil.rmtree(path, ignore_errors=True)

    if not args.skip_translations:
        compile_translations(project_root)

    success = build_executable(
        project_root,
        onefile=args.onefile,
        clean=args.clean,
    )

    if success:
        dist_path = os.path.join(project_root, "dist", "LanguageLearningApp")
        print("\n" + "=" * 60)
        print(" BUILD SUCCESSFUL!")
        print(f" Output location: {dist_path}")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print(" BUILD FAILED! Check console errors above.")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()
