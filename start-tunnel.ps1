$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Menjalankan Backend FastAPI di http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000"

Start-Sleep -Seconds 2
Write-Host "Menjalankan Cloudflare Tunnel... Salin URL https://....trycloudflare.com yang muncul di bawah ke Vercel!" -ForegroundColor Green
& "$root\cloudflared.exe" tunnel --url http://127.0.0.1:8000
