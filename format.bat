@echo off
chcp 65001 > nul
echo ========================================================
echo  Running Formatters and Linters
echo ========================================================
echo.

echo [1/3] Running isort...
isort .
if %errorlevel% neq 0 exit /b %errorlevel%

echo [2/3] Running Black...
black .
if %errorlevel% neq 0 exit /b %errorlevel%

echo [3/4] Running Flake8...
flake8 .
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ Flake8 found issues. Please fix them above.
    exit /b %errorlevel%
)

echo [4/4] Running Mypy...
mypy .
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ Mypy found type errors. Please fix them above.
    exit /b %errorlevel%
)

echo.
echo ✨ All checks passed!
echo ========================================================
pause
