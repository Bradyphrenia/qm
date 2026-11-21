@echo off
setlocal
cd /d "%~dp0"
if defined QM_PYTHON (
    set "QM_BUILD_PYTHON=%QM_PYTHON%"
) else if exist "frontend\.venv\Scripts\python.exe" (
    set "QM_BUILD_PYTHON=%CD%\frontend\.venv\Scripts\python.exe"
) else (
    set "QM_BUILD_PYTHON=python"
)
"%QM_BUILD_PYTHON%" build_tools\build.py --platform windows %*
set "QM_BUILD_RESULT=%ERRORLEVEL%"
endlocal & exit /b %QM_BUILD_RESULT%
