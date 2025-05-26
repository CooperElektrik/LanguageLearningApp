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
echo  LL Project - Main Menu
echo =====================================================================
echo.
echo  Paths are relative to the project root (%SCRIPT_DIR%) unless a full
echo  path is provided when prompted.
echo.
echo  1. Run Language Learning Application
echo  2. Run Course Editor Tool
echo  3. Run Course Content Validator
echo  4. Run CSV to Course Content Importer
echo  5. Create Course Package
echo  6. Compile Main Application (EXE)
echo  7. Compile Course Editor (EXE)
echo  8. Run Automated Tests (pytest)
echo  9. Exit
echo.
set "choice="
set /p choice="Enter your choice (1-9): "

if "%choice%"=="1" goto runApp
if "%choice%"=="2" goto runEditor
if "%choice%"=="3" goto runValidator
if "%choice%"=="4" goto runImporter
if "%choice%"=="5" goto runPackager
if "%choice%"=="6" goto compileApp
if "%choice%"=="7" goto compileEditor
if "%choice%"=="8" goto runTests
if "%choice%"=="9" goto end

echo Invalid choice. Please press any key to try again.
pause >nul
goto menu

:runApp
cls
echo Starting Language Learning Application...
echo Running: python "%SCRIPT_DIR%\application\main.py"
echo.
python "%SCRIPT_DIR%\application\main.py"
echo.
echo Application closed. Press any key to return to the menu.
pause >nul
goto menu

:runEditor
cls
echo Starting Course Editor Tool...
REM The editor is best run as a module from within the 'application' directory
echo Changing directory to: "%SCRIPT_DIR%\application\"
cd /D "%SCRIPT_DIR%\application" 
echo Running: python -m tools.main_editor
echo.
python -m tools.main_editor
echo Changing directory back to: "%SCRIPT_DIR%"
cd /D "%SCRIPT_DIR%"
echo.
echo Editor closed. Press any key to return to the menu.
pause >nul
goto menu

:runValidator
cls
echo --- Course Content Validator ---
echo.
set "manifest_file_input="
set /p manifest_file_input="Enter path to manifest.yaml (e.g., application\manifest.yaml or full path): "

set "full_manifest_path=%manifest_file_input%"
REM Basic check if it's likely an absolute path (contains ':')
echo %manifest_file_input% | find ":" >nul
if errorlevel 1 (
  REM Not an absolute path, assume relative to SCRIPT_DIR
  set "full_manifest_path=%SCRIPT_DIR%\%manifest_file_input%"
)

if not exist "%full_manifest_path%" (
    echo ERROR: Manifest file not found at "%full_manifest_path%"
    pause >nul
    goto menu
)
echo.
echo Running validator on "%full_manifest_path%"...
python "%SCRIPT_DIR%\application\tools\course_validator.py" "%full_manifest_path%"
echo.
echo Validator finished. Press any key to return to the menu.
pause >nul
goto menu

:runImporter
cls
echo --- CSV to Course Content Importer ---
echo.
set "csv_input_file_path="
set /p csv_input_file_path="Enter path to input CSV file (e.g., sample_translations.csv or full path): "

set "full_csv_path=%csv_input_file_path%"
echo %csv_input_file_path% | find ":" >nul
if errorlevel 1 (set "full_csv_path=%SCRIPT_DIR%\%csv_input_file_path%")

if not exist "%full_csv_path%" (
    echo ERROR: CSV input file not found at "%full_csv_path%"
    pause >nul
    goto menu
)

set "yaml_output_file_path="
set /p yaml_output_file_path="Enter path to output course content YAML (e.g., application\course.yaml or full path): "
set "full_yaml_output_path=%yaml_output_file_path%"
echo %yaml_output_file_path% | find ":" >nul
if errorlevel 1 (set "full_yaml_output_path=%SCRIPT_DIR%\%yaml_output_file_path%")

echo.
echo Available exercise types:
echo   translate_to_target
echo   translate_to_source
echo   multiple_choice_translation
set "ex_type="
set /p ex_type="Enter exercise type: "

echo.
set "u_id="
set /p u_id="Enter target Unit ID (e.g., unit1): "
set "l_id="
set /p l_id="Enter target Lesson ID (e.g., u1l1): "
echo.
echo Optional: If the unit or lesson is new, provide titles.
set "u_title="
set /p u_title="Enter Unit Title (if new, otherwise leave blank): "
set "l_title="
set /p l_title="Enter Lesson Title (if new, otherwise leave blank): "

set "command_args="
if defined u_title if not "!u_title!"=="" set command_args=!command_args! --unit_title "!u_title!"
if defined l_title if not "!l_title!"=="" set command_args=!command_args! --lesson_title "!l_title!"

echo.
echo Reminder for default CSV column names:
echo   - 'translate_to_target'/'translate_to_source': 'prompt', 'answer'
echo   - 'multiple_choice_translation': 'source_word', 'correct_option', 
echo     and columns prefixed with 'incorrect_option_' (e.g., 'incorrect_option_1')
echo.
echo To see all options (like custom column names), run:
echo   python "%SCRIPT_DIR%\application\tools\csv_importer.py" --help
echo.
echo Constructing command:
set "final_command=python "%SCRIPT_DIR%\application\tools\csv_importer.py" "%full_csv_path%" --output_yaml "%full_yaml_output_path%" --exercise_type "%ex_type%" --unit_id "%u_id%" --lesson_id "%l_id%" !command_args!"
echo !final_command!
echo.
set "confirm_run="
set /p confirm_run="Run this command? (y/n): "
if /i not "!confirm_run!"=="y" (
    echo Import cancelled by user. Press any key to return to the menu.
    pause >nul
    goto menu
)

!final_command!
echo.
echo CSV Importer finished. Press any key to return to the menu.
pause >nul
goto menu

:runPackager
cls
echo --- Create Course Package ---
echo.
set "manifest_file_packager_input="
set /p manifest_file_packager_input="Enter path to manifest.yaml for the course to package (e.g., application\manifest.yaml or full path): "

set "full_manifest_packager_path=%manifest_file_packager_input%"
echo %manifest_file_packager_input% | find ":" >nul
if errorlevel 1 (set "full_manifest_packager_path=%SCRIPT_DIR%\%manifest_file_packager_input%")

if not exist "%full_manifest_packager_path%" (
    echo ERROR: Manifest file not found at "%full_manifest_packager_path%"
    pause >nul
    goto menu
)

set "output_dir_packager_input="
set /p output_dir_packager_input="Enter output directory for the package (leave blank for same as manifest): "

set "command_args_packager="
if defined output_dir_packager_input if not "!output_dir_packager_input!"=="" (
    set "full_output_dir_packager="
    echo !output_dir_packager_input! | find ":" >nul
    if errorlevel 1 (
        set "full_output_dir_packager=!SCRIPT_DIR!\!output_dir_packager_input!"
    ) else (
        set "full_output_dir_packager=!output_dir_packager_input!"
    )
    set command_args_packager=!command_args_packager! --output_dir "!full_output_dir_packager!"
)

set "package_name_input="
set /p package_name_input="Enter custom package name (e.g., 'my_course_v1', leave blank for default): "
if defined package_name_input if not "!package_name_input!"=="" set command_args_packager=!command_args_packager! --name "!package_name_input!"

echo.
echo Constructing command:
set "final_packager_command=python "%SCRIPT_DIR%\application\tools\course_packager.py" "%full_manifest_packager_path%" !command_args_packager!"
echo !final_packager_command!
echo.
set "confirm_run_packager="
set /p confirm_run_packager="Run this command? (y/n): "
if /i not "!confirm_run_packager!"=="y" (
    echo Packaging cancelled by user. Press any key to return to the menu.
    pause >nul
    goto menu
)

!final_packager_command!
echo.
echo Course Packager finished. Press any key to return to the menu.
pause >nul
goto menu

:compileApp
cls
echo =====================================================================
echo  Compiling Main Application to Executable (using Nuitka)
echo =====================================================================
echo.
echo This process can take a while. Please do not close the window.
echo Output will be in: "%SCRIPT_DIR%\application\dist\"
echo.
echo Changing directory to: "%SCRIPT_DIR%\application\"
cd /D "%SCRIPT_DIR%\application"
echo Running Nuitka...
nuitka --standalone --onefile --windows-disable-console --plugin-enable=pyside6 --include-qt-plugins=platforms,styles,imageformats --include-data-files="manifest.yaml=manifest.yaml" --include-data-files="esperanto_course.yaml=esperanto_course.yaml" --output-dir=dist main.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Nuitka compilation failed for Main Application.
    echo Please check the console output above for details.
) else (
    echo.
    echo Nuitka compilation successful for Main Application.
    echo Executable located at: "%SCRIPT_DIR%\application\dist\main.exe"
)
echo.
echo Press any key to return to the menu.
pause >nul
cd /D "%SCRIPT_DIR%"
goto menu

:compileEditor
cls
echo =====================================================================
echo  Compiling Course Editor to Executable (using Nuitka)
echo =====================================================================
echo.
echo This process can take a while. Please do not close the window.
echo Output will be in: "%SCRIPT_DIR%\application\dist\"
echo.
echo Changing directory to: "%SCRIPT_DIR%\application\"
cd /D "%SCRIPT_DIR%\application"
echo Running Nuitka...
REM The editor does not include specific course data, it loads it.
nuitka --standalone --onefile --windows-disable-console --plugin-enable=pyside6 --include-qt-plugins=platforms,styles,imageformats --output-dir=dist tools/main_editor.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Nuitka compilation failed for Course Editor.
    echo Please check the console output above for details.
) else (
    echo.
    echo Nuitka compilation successful for Course Editor.
    echo Executable located at: "%SCRIPT_DIR%\application\dist\main_editor.exe"
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
REM Pytest is typically run from the project root where pyproject.toml or setup.cfg might be,
REM and where it can easily discover the 'tests' directory and the 'application' package.
echo Changing directory to: "%SCRIPT_DIR%\"
cd /D "%SCRIPT_DIR%"
echo Running: pytest -v
pytest -v
REM -v for verbose output
REM Add other pytest options as needed, e.g., -k "test_specific_function"
REM or --cov=application to check test coverage
echo.
echo Tests finished. Press any key to return to the menu.
pause >nul
goto menu

:end
cls
echo Exiting LL Project Menu. Goodbye!
if defined VIRTUAL_ENV (
    echo.
    echo Virtual environment was active. You might need to manually type 'deactivate' 
    echo or close this window to fully exit the venv session if it was sourced.
)
pause >nul
endlocal
exit /b