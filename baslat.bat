@echo off
title LocalMind - Yerel RAG Asistani
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo           LocalMind Baslatiliyor...
echo ===================================================
echo.

if not exist "venv\Scripts\streamlit.exe" (
    echo [HATA] Sanal ortam (venv) bulunamadi!
    echo Lutfen once gereksinimleri yukleyin.
    echo.
    pause
    exit /b 1
)

echo Tarayici aciliyor, lutfen bekleyin...
echo (Kapatmak istediginizde bu pencereyi kapatabilir veya Ctrl+C yapabilirsiniz)
echo.

venv\Scripts\streamlit.exe run app.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [HATA] Bir sorun olustu.
    pause
)

