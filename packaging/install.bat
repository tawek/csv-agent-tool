@echo off
setlocal
title Product Description Tool Installer

set "DIST_DIR=%~dp0"
if "%DIST_DIR:~-1%"=="\" set "DIST_DIR=%DIST_DIR:~0,-1%"
set "INSTALL_DIR=C:\apps\product-description-tool"

echo ============================================================
echo Product Description Tool Installer
echo ============================================================
echo Source: %DIST_DIR%
echo Destination: %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%" (
    echo Creating destination directory...
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 (
        echo Failed to create destination directory.
        pause
        exit /b 1
    )
)

echo Copying files. This may take a while for large builds...
echo.

where robocopy >nul 2>&1
if errorlevel 1 goto use_xcopy

set "COPY_TOOL=robocopy"
echo Using robocopy.
echo robocopy output follows:
echo.
robocopy "%DIST_DIR%" "%INSTALL_DIR%" /E /R:2 /W:2
set "RC=%ERRORLEVEL%"

if %RC% GEQ 8 (
    echo.
    echo Installation failed. robocopy exit code: %RC%
    pause
    exit /b %RC%
)

goto install_done

:use_xcopy
set "COPY_TOOL=xcopy"
echo robocopy is not available on this system.
echo Falling back to xcopy.
echo xcopy output follows:
echo.
xcopy "%DIST_DIR%*" "%INSTALL_DIR%\" /E /I /Y
if errorlevel 1 (
    echo.
    echo Installation failed during xcopy.
    pause
    exit /b 1
)
set "RC=0"

:install_done

echo.
echo Installation complete using %COPY_TOOL%. Exit code: %RC%
echo Launch with: %INSTALL_DIR%\product-description-tool.exe
pause
