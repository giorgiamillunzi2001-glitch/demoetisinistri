@echo off
cd /d "%~dp0"
echo ================================================
echo   Avvio di RetiSinistri
echo   Il browser si aprira' tra qualche secondo su:
echo   http://localhost:8501
echo   (non chiudere questa finestra mentre usi l'app)
echo ================================================
start "" /b cmd /c "timeout /t 6 /nobreak >nul & start "" http://localhost:8501"
py -m streamlit run app\main.py --server.headless true --server.port 8501 --browser.gatherUsageStats false
echo.
echo L'app si e' chiusa. Se vedi un errore qui sopra, copialo e invialo.
pause
