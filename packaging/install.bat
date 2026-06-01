@echo off
setlocal
echo Installing Product Description Tool to C:\apps\...

set "DIST_DIR=%~dp0"
set "INSTALL_DIR=C:\apps\product-description-tool"

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

xcopy "%DIST_DIR%*" "%INSTALL_DIR%\" /E /I /Y >nul 2>&1
if errorlevel 1 (
    echo Failed to copy files.
    pause
    exit /b 1
)

echo.
echo Installation complete.
echo Launch with: %INSTALL_DIR%\product-description-tool.exe
pause
