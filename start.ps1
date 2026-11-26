$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Menjalankan Backend FastAPI di http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\backend'; .\venv\Scripts\uvicorn.exe main:app --host 127.0.0.1 --port 8000"

Write-Host "Menjalankan Frontend Vite di http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root\frontend'; npm run dev"
