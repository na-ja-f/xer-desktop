@echo off
echo.
echo ==========================================
echo   XER Assistant Enterprise Builder
echo ==========================================
echo.

:: Set root directory relative to this script
set ROOT_DIR=%~dp0..
set PYTHON_VENV=%ROOT_DIR%\venv_desktop\Scripts\python.exe

:: 1. Compile Python Backend
echo [1/4] Compiling Python Backend (PyInstaller)...

if not exist "%PYTHON_VENV%" (
    echo Python virtual environment not found at %PYTHON_VENV%
    echo Please run setup_windows.bat first.
    exit /b 1
)

cd /d "%ROOT_DIR%\engine"

:: Ensure pyinstaller is installed
"%PYTHON_VENV%" -m pip install pyinstaller

:: Build executable to dist/backend
"%PYTHON_VENV%" -m PyInstaller --name backend --onefile --noconsole main.py
if %errorlevel% neq 0 (
    echo Error compiling Python backend.
    exit /b %errorlevel%
)
cd /d "%ROOT_DIR%"

:: 2. Build React Frontend
echo [2/4] Building React Frontend...
cd /d "%ROOT_DIR%\app\renderer"
call npm run build
if %errorlevel% neq 0 (
    echo Error building frontend.
    exit /b %errorlevel%
)
cd /d "%ROOT_DIR%"

:: 3. Compile Electron main/bridge TypeScript
echo [3/4] Compiling Electron main/bridge TypeScript...
call npx tsc -p tsconfig.electron.json
if %errorlevel% neq 0 (
    echo Error compiling Electron TypeScript.
    exit /b %errorlevel%
)

:: 4. Package Electron Application
echo [4/4] Packaging Electron Application...
call npx electron-builder --win
if %errorlevel% neq 0 (
    echo Error packaging Electron application.
    exit /b %errorlevel%
)

echo.
echo ==========================================
echo   Build Complete!
echo   Installer can be found in dist/
echo ==========================================
pause
