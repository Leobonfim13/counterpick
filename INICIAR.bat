@echo off
chcp 65001 >nul
title CounterPick
cd /d "%~dp0"

python -c "import flask, cv2, numpy" 2>nul
if errorlevel 1 (
    echo Preparando o sistema pela primeira vez, aguarde...
    python -m pip install -r requirements.txt
)

if not exist ".env" (
    copy ".env.exemplo" ".env" >nul
    echo Criei o arquivo .env. Abra ele no Bloco de Notas e cole a sua chave da Riot.
)

start "" http://localhost:5002
python app.py
pause
