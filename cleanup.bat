@echo off
setlocal enabledelayedexpansion

echo ========================================
echo   GeekClock Cleanup Script
echo ========================================
echo.

:: ---- 1. Delete __pycache__ directories ----
echo [1/5] Cleaning __pycache__ ...
set count=0
for /d /r "%~dp0" %%d in (__pycache__) do (
    if exist "%%d" (
        echo   Deleting: %%d
        rd /s /q "%%d"
        set /a count+=1
    )
)
echo   Deleted !count! __pycache__ dir(s)

:: ---- 2. Delete .pyc files ----
echo.
echo [2/5] Cleaning .pyc files ...
set count=0
for /r "%~dp0" %%f in (*.pyc) do (
    echo   Deleting: %%f
    del /q "%%f"
    set /a count+=1
)
echo   Deleted !count! .pyc file(s)

:: ---- 3. Delete build/ (PyInstaller temp) ----
echo.
echo [3/5] Cleaning build/ ...
if exist "%~dp0build" (
    rd /s /q "%~dp0build"
    echo   Deleted build/
) else (
    echo   build/ not found, skip
)

:: ---- 4. Delete dist/ (PyInstaller output) ----
echo.
echo [4/5] Cleaning dist/ ...
if exist "%~dp0dist" (
    rd /s /q "%~dp0dist"
    echo   Deleted dist/
) else (
    echo   dist/ not found, skip
)

:: ---- 5. Delete .spec file ----
echo.
echo [5/5] Cleaning .spec file ...
if exist "%~dp0GeekClock.spec" (
    del /q "%~dp0GeekClock.spec"
    echo   Deleted GeekClock.spec
) else (
    echo   GeekClock.spec not found, skip
)

echo.
echo ========================================
echo   Cleanup complete!
echo ========================================
echo.
echo Tip: Run build.bat to rebuild the .exe
echo.

pause
