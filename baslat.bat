@echo off
setlocal EnableExtensions DisableDelayedExpansion
title LocalMind - Yerel RAG Asistani
chcp 65001 >nul 2>&1

pushd "%~dp0" 2>nul || (
    echo [HATA] Proje klasorune girilemedi: %~dp0
    pause
    exit /b 1
)

echo ===================================================
echo           LocalMind Baslatiliyor...
echo ===================================================
echo.

if not exist "app.py" (
    echo [HATA] app.py bulunamadi.
    echo baslat.bat dosyasini proje klasorunden calistirin.
    echo.
    popd
    pause
    exit /b 1
)

rem Streamlit'in gercekten kurulu oldugu ilk Python ortamini kullan.
rem Bos veya eksik bir sanal ortam varsa otomatik olarak digerine gecer.
set "PYTHON_EXE="
call :try_python ".venv\Scripts\python.exe"
call :try_python "venv\Scripts\python.exe"

if not defined PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import streamlit" >nul 2>&1
        if not errorlevel 1 set "PYTHON_EXE=python"
    )
)

if not defined PYTHON_EXE (
    echo [HATA] Streamlit kurulu bir Python ortami bulunamadi.
    echo.
    echo Python kuruluysa su komutu calistirin:
    echo     python -m pip install -r requirements.txt
    echo.
    popd
    pause
    exit /b 1
)

echo Kullanilan Python: %PYTHON_EXE%
echo Tarayici aciliyor, lutfen bekleyin...
echo Kapatmak icin bu pencereyi kapatin veya Ctrl+C tuslarina basin.
echo.

"%PYTHON_EXE%" -m streamlit run "app.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [HATA] LocalMind baslatilamadi. Hata kodu: %EXIT_CODE%
    echo Yukaridaki hata mesajini kontrol edin.
    echo.
    popd
    pause
    exit /b %EXIT_CODE%
)

popd
exit /b 0

:try_python
if defined PYTHON_EXE exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import streamlit" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=%~1"
exit /b 0

