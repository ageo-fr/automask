@echo off
chcp 65001 >nul
setlocal

echo.
echo ========================================
echo   AUTOMASK
echo.
echo   Automask est un outil de segmentation d'images
echo   développé par AGEO avec le soutien du SRA Bretagne.
echo ========================================
echo.

REM -------------------- Se placer dans le dossier du script --------------------
SET SCRIPT_DIR=%~dp0
SET ROOT_DIR=%SCRIPT_DIR%
CD /D "%ROOT_DIR%"

REM -------------------- Chemins --------------------
SET VENV_DIR=%ROOT_DIR%\venv
SET PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
SET AUTOMASK_SCRIPT=%ROOT_DIR%\code\automask.py

REM -------------------- Vérifications --------------------
IF NOT EXIST "%PYTHON_EXE%" (
    echo Erreur : python.exe du venv introuvable
    echo Chemin attendu : %PYTHON_EXE%
    echo Veuillez lancer install.bat
    pause
    exit /b 1
)

IF NOT EXIST "%AUTOMASK_SCRIPT%" (
    echo Erreur : automask.py introuvable
    echo Chemin attendu : %AUTOMASK_SCRIPT%
    pause
    exit /b 1
)

REM -------------------- Lancer Automask --------------------
echo.
echo Lancement d'AutoMask ...
echo (veuillez patienter quelques secondes)
echo.

"%PYTHON_EXE%" "%AUTOMASK_SCRIPT%"
IF ERRORLEVEL 1 (
    echo.
    echo [ERREUR] Automask a échoué
)

echo.
echo ... Fermeture d'AutoMask.
pause
