@echo off
echo.
echo   Rizzi CMS - avvio...
echo.
pip install flask pillow -q
start "" "http://localhost:5151"
python app.py
pause
