@echo off
setlocal enabledelayedexpansion

:: Get the directory of this batch script (assumed to be project root)
SET "SCRIPT_DIR=%~dp0"
REM Remove trailing backslash from SCRIPT_DIR if it exists, for cleaner path joining
IF "%SCRIPT_DIR:~-1%"=="\" SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

:: --- Optional: Activate virtual environment ---
IF EXIST "%SCRIPT_DIR%\venv\Scripts\activate.bat" (
    echo Activating virtual environment from "%SCRIPT_DIR%\venv\"...
    call "%SCRIPT_DIR%\venv\Scripts\activate.bat"
    echo Virtual environment activated.
    echo.
) ELSE (
    echo Virtual environment not found at "%SCRIPT_DIR%\venv\".
    echo Proceeding with the current Python environment.
    echo Please ensure PySide6, PyYAML, Nuitka, and pytest are installed.
    echo.
)

:menu
cls
echo =====================================================================
echo  LinguaLearn Project Menu
echo =====================================================================
echo.
echo  1. Run Main Application (Learning Mode)
echo  2. Open Course Editor
echo  3. Compile Application to EXE (with Nuitka)
echo  4. Compile Application to EXE (with PyInstaller)
echo  5. Run Automated Tests (with pytest)
echo  6. Exit
echo.
set "choice="
set /p choice="Enter your choice (1-6): "

if "%choice%"=="1" goto runApp
if "%choice%"=="2" goto runEditor
if "%choice%"=="3" goto compileApp
if "%choice%"=="4" goto compileAppPyInstaller
if "%choice%"=="5" goto runTests
if "%choice%"=="6" goto end

echo Invalid choice. Please press any key to try again or close the window.
pause >nul
goto menu

:runApp
cls
echo Starting LinguaLearn Application...
echo Running: python "%SCRIPT_DIR%\application\main.py"
echo.
python "%SCRIPT_DIR%\application\main.py"
echo.
echo Application closed. Press any key to return to the menu.
pause >nul
goto menu

:runEditor
cls
echo Starting LinguaLearn Course Editor...
echo Running: python -m application.tools.main_editor
echo.
python -m application.tools.main_editor
echo.
echo Editor closed. Press any key to return to the menu.
pause >nul
goto menu

:compileApp
cls
echo =====================================================================
echo  Compiling Main Application to Executable (using Nuitka)
echo =====================================================================
echo.
echo This process can take a while. Please do not close the window.
echo The final executable will be placed in: "%SCRIPT_DIR%\application\dist\"
echo.
echo Changing directory to: "%SCRIPT_DIR%\application\"
cd /D "%SCRIPT_DIR%\application"
echo Running Nuitka...
echo.

REM The --include-data-dir="courses=courses" flag is crucial.
REM It bundles all courses within the 'courses' directory, making the app self-contained.
python -m nuitka ^
  --standalone ^
  --enable-plugin=pyside6 ^
  --nofollow-import-to=torch ^
  --nofollow-import-to=ctranslate2 ^
  --nofollow-import-to=huggingface_hub ^
  --nofollow-import-to=PIL ^
  --show-memory ^
  --mingw64 ^
  --include-data-dir="courses=courses" ^
  --include-data-dir="assets=assets" ^
  --include-data-dir="ui/styles=ui/styles" ^
  --include-data-dir="localization=localization" ^
  --output-dir=dist ^
  main.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Nuitka compilation failed.
    echo Please check the console output above for details.
) else (
    echo.
    echo Nuitka compilation successful.
    echo Executable located at: "%SCRIPT_DIR%\application\dist\main.exe"
)
echo.
echo Press any key to return to the menu.
pause >nul
cd /D "%SCRIPT_DIR%"
goto menu

:compileAppPyInstaller
cls
echo =====================================================================
echo  Compiling Main Application to Executable (using PyInstaller)
echo =====================================================================
echo.
echo This process can take a while. Please do not close the window.
echo The final executable will be placed in: "%SCRIPT_DIR%\application\dist\"
echo.
echo Changing directory to: "%SCRIPT_DIR%\application\"
cd /D "%SCRIPT_DIR%\application"
echo Running PyInstaller...
echo.

REM --onefile: Creates a single executable file.
REM --windowed: Prevents a console window from opening when the app runs.
REM --distpath dist: Specifies the output directory for the executable.
REM --add-data "source;destination": Includes data files/directories.
REM The format is "source_path;destination_in_bundle" for Windows.
pyinstaller ^
  --onefile ^
  --windowed ^
  --distpath dist ^
  --add-data "courses;courses" ^
  --add-data "assets;assets" ^
  --add-data "ui/styles;ui/styles" ^
  --add-data "localization;localization" ^
  main.py

if %errorlevel% neq 0 (
    echo.
    echo ERROR: PyInstaller compilation failed.
    echo Please check the console output above for details.
) else (
    echo.
    echo PyInstaller compilation successful.
    echo Executable located at: "%SCRIPT_DIR%\application\dist\main.exe"
)
echo.
echo Press any key to return to the menu.
pause >nul
goto menu

:runTests
cls
echo =====================================================================
echo  Running Automated Tests (pytest)
echo =====================================================================
echo.
echo Pytest will discover and run tests in the 'tests' directory.
echo Ensure pytest is installed in your environment.
echo.
echo Changing directory to project root: "%SCRIPT_DIR%\"
cd /D "%SCRIPT_DIR%"
echo Running: pytest -v
pytest -v
echo.
echo Tests finished. Press any key to return to the menu.
pause >nul
goto menu

:end
cls
echo Exiting LL Project Menu. Goodbye!
if defined VIRTUAL_ENV (
    echo.
    echo Virtual environment was active. You may need to manually type 'deactivate' 
    echo or close this window to fully exit the venv session.
)
pause >nul
endlocal
exit /b