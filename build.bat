@echo off
cd /d "%~dp0"
echo Installation des dependances...
python -m pip install --upgrade pystray pillow pyperclip pyinstaller
echo.
echo Compilation...
python -m PyInstaller --onefile --noconsole --clean --name QuickAsk --hidden-import pystray._win32 quickask.py
echo.
echo Fini : dist\QuickAsk.exe
pause
