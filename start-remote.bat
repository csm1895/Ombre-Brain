@echo off
echo === Starting Ombre Brain (streamable-http) ===

set OMBRE_API_KEY=sk-zlZ311bbf91bef49ed5dedeb59363841210445e9146OV5hq
set OMBRE_TRANSPORT=streamable-http

cd /d C:\Users\86150\Ombre-Brain

start "Ombre Brain" cmd /c "venv\Scripts\python.exe server.py"

timeout /t 3 /nobreak >nul

echo === Starting Cloudflare Tunnel ===
cloudflared tunnel --url http://localhost:8000

pause
