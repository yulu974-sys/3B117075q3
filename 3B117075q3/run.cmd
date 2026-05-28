@echo off
set FLASK_APP=app.py
set FLASK_RUN_HOST=0.0.0.0
set FLASK_RUN_PORT=80

if not exist logs mkdir logs

flask run --host=0.0.0.0 --port=80
pause
