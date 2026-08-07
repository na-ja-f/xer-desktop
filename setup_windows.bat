@echo off
echo.
echo ==========================================
echo   XER Assistant Windows Setup Script
echo ==========================================
echo.

:: 1. Main Directory
echo [1/3] Installing root dependencies...
call npm install
if %errorlevel% neq 0 (
    echo Error installing root dependencies.
    exit /b %errorlevel%
)

:: 2. Renderer Directory
echo [2/3] Installing renderer dependencies...
cd app\renderer
call npm install
cd ..\..
if %errorlevel% neq 0 (
    echo Error installing renderer dependencies.
    exit /b %errorlevel%
)

:: 3. Python Virtual Environment
echo [3/3] Setting up Python virtual environment...
if not exist "venv_desktop" (
    echo Attempting to create virtual environment...
    python -m venv venv_desktop && goto venv_ok
    py -m venv venv_desktop && goto venv_ok
    python3 -m venv venv_desktop && goto venv_ok
    
    echo.
    echo ERROR: Could not find 'python', 'py', or 'python3' to create venv.
    echo Please ensure Python is installed and added to your PATH.
    pause
    exit /b 1
)

:venv_ok
echo Virtual environment 'venv_desktop' ready.

echo.
echo Installing Python backend dependencies...
venv_desktop\Scripts\python.exe -m pip install -r engine/requirements.txt
if %errorlevel% neq 0 (
    echo Error installing Python dependencies.
    exit /b %errorlevel%
)

echo.
echo ==========================================
echo   Setup Complete! 
echo.
echo   You can now start the application by running:
echo   npm run dev
echo ==========================================
pause
