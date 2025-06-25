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
    echo Please ensure PySide6, PyYAML, Nuitka, PyInstaller, and pytest are installed.
    echo.
)

:menu
cls
echo =====================================================================
echo  Project Menu
echo =====================================================================
echo.
echo  1. Run Main Application (Learning Mode)
echo  2. Open Course Editor
echo  3. Compile Application to EXE (with Nuitka)
echo  4. Compile Application to EXE (with PyInstaller) 
echo  5. Run Automated Tests (with pytest)
echo  6. Update/Compile Translations
echo  7. Exit
echo.
set "choice="
set /p choice="Enter your choice (1-7): "

if "%choice%"=="1" goto runApp
if "%choice%"=="2" goto runEditor
if "%choice%"=="3" goto compileNuitka
if "%choice%"=="4" goto compilePyInstaller
if "%choice%"=="5" goto runTests
if "%choice%"=="6" goto updateTranslations
if "%choice%"=="7" goto end

echo Invalid choice. Please press any key to try again.
pause >nul
goto menu

:runApp
cls
echo Starting Application...
echo Running: python "%SCRIPT_DIR%\application\main.py"
echo.
python "%SCRIPT_DIR%\application\main.py"
echo.
echo Application closed. Press any key to return to the menu.
pause >nul
goto menu

:runEditor
cls
echo Starting Course Editor...
echo Running: python -m application.tools.main_editor
echo.
python -m application.tools.main_editor
echo.
echo Editor closed. Press any key to return to the menu.
pause >nul
goto menu

:compileNuitka
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
  --module-parameter=torch-disable-jit=yes ^
  --mingw64 ^
  --include-data-dir="courses=courses" ^
  --include-data-dir="assets=assets" ^
  --include-data-dir="models=models" ^
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

:compilePyInstaller
cls
echo =====================================================================
echo  Compiling Main Application to Executable (using PyInstaller)
echo =====================================================================
echo.
echo This may take several minutes. Please wait...
echo The compiled executable will be placed in: "%SCRIPT_DIR%\application\dist\"
echo.
echo Changing directory to: "%SCRIPT_DIR%\application\"
cd /D "%SCRIPT_DIR%\application"

echo Generating spec file and building with PyInstaller...
echo.

REM Generate spec file only once if not already present
if not exist "main.spec" (
    pyinstaller --name=main --onefile --specpath=. main.py
)

REM Modify spec file or manually add datas entries here if needed
REM For now, we use --add-data to include required directories

REM Build using PyInstaller with added data directories
pyinstaller ^
  --onedir ^
  --windowed ^
  --paths "%SCRIPT_DIR%\application" ^
  --add-data="courses;courses" ^
  --add-data="assets;assets" ^
  --add-data="models;models" ^
  --add-data="ui/styles;ui/styles" ^
  --add-data="localization;localization" ^
  --distpath=dist ^
  --workpath=build ^
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
cd /D "%SCRIPT_DIR%"
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

:updateTranslations
cls
echo =====================================================================
echo  Updating and Compiling Translations
echo =====================================================================
echo.
echo Running pyside6-lupdate...
echo.
pyside6-lupdate ^
  "%SCRIPT_DIR%\application\main.py" ^
  "%SCRIPT_DIR%\application\ui\main_window.py" ^
  "%SCRIPT_DIR%\application\ui\views\course_editor_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\course_overview_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\course_selection_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\glossary_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\lesson_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\progress_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\review_view.py" ^
  "%SCRIPT_DIR%\application\ui\views\base_exercise_player_view.py" ^
  "%SCRIPT_DIR%\application\ui\dialogs\settings_dialog.py" ^
  "%SCRIPT_DIR%\application\ui\dialogs\initial_audio_setup_dialog.py" ^
  "%SCRIPT_DIR%\application\ui\dialogs\glossary_detail_dialog.py" ^
  "%SCRIPT_DIR%\application\ui\dialogs\glossary_lookup_dialog.py" ^
  "%SCRIPT_DIR%\application\ui\dialogs\dev_info_dialog.py" ^
  "%SCRIPT_DIR%\application\ui\widgets\exercise_widgets.py" ^
  "%SCRIPT_DIR%\application\core\course_manager.py" ^
  -ts "%SCRIPT_DIR%\application\localization\app_zh-TW.ts" ^
     "%SCRIPT_DIR%\application\localization\app_vi-VN.ts" ^
     "%SCRIPT_DIR%\application\localization\app_ja-JP.ts" ^
     "%SCRIPT_DIR%\application\localization\app_ru-RU.ts" ^
     "%SCRIPT_DIR%\application\localization\app_ko-KR.ts" ^
     "%SCRIPT_DIR%\application\localization\app_de-DE.ts"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: pyside6-lupdate failed.
    echo Please check the console output above for details.
    pause >nul
    goto menu
)

echo.
echo Running pyside6-lrelease...
echo.
pyside6-lrelease ^
  -compress ^
  "%SCRIPT_DIR%\application\localization\app_de-DE.ts" ^
  "%SCRIPT_DIR%\application\localization\app_ja-JP.ts" ^
  "%SCRIPT_DIR%\application\localization\app_ko-KR.ts" ^
  "%SCRIPT_DIR%\application\localization\app_ru-RU.ts" ^
  "%SCRIPT_DIR%\application\localization\app_vi-VN.ts" ^
  "%SCRIPT_DIR%\application\localization\app_zh-TW.ts"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: pyside6-lrelease failed.
    echo Please check the console output above for details.
) else (
    echo.
    echo Translation compilation successful.
)
echo.
echo Press any key to return to the menu.
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