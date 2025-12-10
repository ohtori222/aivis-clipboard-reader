@echo off
chcp 65001 > nul
echo ========================================================
echo  AivisSpeech Clipboard Reader - Build Script
echo ========================================================

echo.
echo [1/3] Checking PyInstaller...
pip show pyinstaller > nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
) else (
    echo PyInstaller is ready.
)

echo.
echo [2/3] Detecting CustomTkinter path...
for /f "delims=" %%i in ('python -c "import customtkinter; import os; print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
echo CustomTkinter detected at: %CTK_PATH%

echo.
echo [3/3] Building Executable...
echo This may take a while...

pyinstaller --noconsole --onefile --clean ^
    --name "AivisClipboardReader" ^
    --icon "icon.ico" ^
    --add-data "icon.ico;." ^
    --add-data "%CTK_PATH%;customtkinter" ^
    --collect-all "src" ^
    --paths "src" ^
    src\aivis_gui.py

if %errorlevel% equ 0 (
    echo.
    echo [4/4] Copying assets to dist folder...
    copy README.md dist\ > nul
    copy config.json dist\ > nul

    REM 配布用にはサンプルアートワークを含める
    if exist cover_sample.jpg copy cover_sample.jpg dist\ > nul
    if exist cover_sample.png copy cover_sample.png dist\ > nul

    echo.
    echo ========================================================
    echo.

    if "%CI%"=="true" (
        echo Skipping explorer open and pause for CI environment.
    ) else (
        start explorer dist
        pause
    )
) else (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo  Build Failed. Please check the error messages above.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    if "%CI%" neq "true" pause
)
