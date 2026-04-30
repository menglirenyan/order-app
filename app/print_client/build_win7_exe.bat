@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements-win7.txt
pyinstaller --onefile --noconsole --name fy_print_client fy_print_client.py
if not exist dist\config.json copy config.example.json dist\config.json
echo Build complete: dist\fy_print_client.exe
echo Edit dist\config.json before installing auto start.
pause
