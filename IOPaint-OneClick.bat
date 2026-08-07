@echo off
setlocal EnableDelayedExpansion
REM ============================================================
REM  IOPaint one-click launcher for Windows
REM  - First run: installs uv, creates a Python env, installs
REM    PyTorch (CUDA 12.8 if an NVIDIA GPU is present, else CPU)
REM    and the latest IOPaint release wheel from GitHub.
REM  - Later runs: starts IOPaint immediately.
REM  Everything is installed under %LOCALAPPDATA%\IOPaint.
REM ============================================================

set "REPO=daraskme/IOpaint"
set "APPDIR=%LOCALAPPDATA%\IOPaint"
set "VENV=%APPDIR%\env"
set "IOPAINT_EXE=%VENV%\Scripts\iopaint.exe"

if exist "%IOPAINT_EXE%" goto :run

echo === IOPaint first-time setup ===
echo Install location: %APPDIR%
echo.

where uv >nul 2>nul
if not errorlevel 1 goto :have_uv
echo [1/4] Installing uv package manager...
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
set "PATH=%USERPROFILE%\.local\bin;%PATH%"
where uv >nul 2>nul
if errorlevel 1 (
    echo ERROR: uv installation failed. Install it manually from https://docs.astral.sh/uv/
    goto :fail
)
:have_uv

echo [2/4] Creating Python environment...
if not exist "%APPDIR%" mkdir "%APPDIR%"
uv venv "%VENV%" --python 3.12
if errorlevel 1 goto :fail

where nvidia-smi >nul 2>nul
if errorlevel 1 goto :torch_cpu
echo [3/4] NVIDIA GPU detected - installing PyTorch with CUDA 12.8...
echo       NOTE: needs a driver supporting CUDA 12.8+ (Blackwell/Ada/Ampere are fine).
uv pip install --python "%VENV%" torch torchvision --torch-backend=cu128
if errorlevel 1 (
    echo ERROR: CUDA PyTorch install failed. Update your NVIDIA driver and retry.
    goto :fail
)
goto :torch_done
:torch_cpu
echo [3/4] No NVIDIA GPU detected - installing CPU PyTorch...
uv pip install --python "%VENV%" torch torchvision --torch-backend=cpu
if errorlevel 1 goto :fail
:torch_done

echo [4/4] Downloading the latest IOPaint release...
set "WHEEL_URL="
for /f "usebackq delims=" %%u in (`powershell -NoProfile -Command "$r = Invoke-RestMethod 'https://api.github.com/repos/%REPO%/releases?per_page=5'; $a = $r | ForEach-Object assets | Where-Object name -like '*.whl' | Select-Object -First 1; $a.browser_download_url"`) do set "WHEEL_URL=%%u"
if "!WHEEL_URL!"=="" (
    echo ERROR: could not find a release wheel for %REPO%.
    goto :fail
)
echo       %WHEEL_URL%
uv pip install --python "%VENV%" "!WHEEL_URL!"
if errorlevel 1 goto :fail

echo.
echo Setup finished successfully.
echo.

:run
where nvidia-smi >nul 2>nul
if errorlevel 1 (set "DEVICE=cpu") else (set "DEVICE=cuda")
echo Starting IOPaint (device: !DEVICE!) - the browser will open automatically.
echo Close this window to stop IOPaint.
"%IOPAINT_EXE%" start --model lama --device !DEVICE! --port 8080 --inbrowser
goto :eof

:fail
echo.
echo Setup failed. See the messages above for details.
pause
exit /b 1
