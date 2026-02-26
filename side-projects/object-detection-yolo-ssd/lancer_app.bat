@echo off
echo ================================
echo   Detection d objets : Projet M1
echo ================================
echo.
echo Lancement de l'application Streamlit...

:: Vérifier que streamlit est installé, sinon l’installer
pip show streamlit >nul 2>&1
IF ERRORLEVEL 1 (
    echo Streamlit n'est pas installé. Installation en cours...
    pip install streamlit
)

streamlit run app.py
pause
