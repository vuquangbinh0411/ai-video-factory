@echo off
chcp 65001 >nul
title AI Video Factory Studio (Google Veo 2 Engine)

echo ============================================================
echo   AI VIDEO FACTORY STUDIO - HE THONG TAO VIDEO DONG BO
echo ============================================================
echo.

cd /d "%~dp0"

:: 1. Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay Python! Vui long cai dat Python 3.10 tro len va tich vao "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: 2. Tu dong giai phong cong 7860 neu co tien trinh cu con treo
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":7860" ^| findstr "LISTENING"') do (
    echo [Khoi dong] Giai phong tien trinh cu tren cong 7860 - PID: %%a
    taskkill /f /pid %%a >nul 2>&1
)

echo Dang khoi dong Web Dashboard tai http://localhost:7860 ...
echo Trinh duyet se tu dong mo len trong giay lat!
echo.
echo [HUONG DAN TAT UNG DUNG DONG BO]:
echo   - Cach 1: Bam nut 'Tat App' mau do ngay tren goc phai Web UI.
echo   - Cach 2: Nhan giu Ctrl + C hoac dong cua so Command Prompt nay.
echo ============================================================
echo.

:: 3. Tu dong mo trinh duyet sau 2 giay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:7860"

:: 4. Chay Studio chinh
python scripts\web_ui.py

:: 5. Khi nguoi dung dong console, dam bao don sach toan bo tien trinh con
echo.
echo [Thoat] Dang don dep toan bo tien trinh FFmpeg va giai phong bo nho...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":7860" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
)
taskkill /f /im ffmpeg.exe >nul 2>&1
echo Da tat hoan tat.
