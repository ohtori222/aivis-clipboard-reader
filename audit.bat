@echo off
chcp 65001 > nul
echo ========================================================
echo  Running Dependency Vulnerability Audit
echo ========================================================
echo.

pip-audit
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ Vulnerabilities found! Please check the report above.
    exit /b %errorlevel%
)

echo.
echo ✨ No known vulnerabilities found!
echo ========================================================
pause
