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
    --add-data "%CTK_PATH%;customtkinter" ^
    --collect-all "aivis_reader" ^
    aivis_gui.py

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo  Build Successful!
    echo  Executable is located in: dist\AivisClipboardReader.exe
    echo ========================================================
    echo.
    pause
) else (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo  Build Failed. Please check the error messages above.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    pause
)
