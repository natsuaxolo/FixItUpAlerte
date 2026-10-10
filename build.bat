@echo off
cd /d "%~dp0"

echo === 1/3 Installation des bibliotheques ===
python -m pip install customtkinter mss opencv-python numpy pytesseract pyinstaller
if errorlevel 1 goto erreur

echo === 2/3 Copie de Tesseract (si absent du dossier) ===
if not exist "Tesseract-OCR\tesseract.exe" (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        xcopy "C:\Program Files\Tesseract-OCR" "Tesseract-OCR\" /E /I /Y
    ) else (
        echo Tesseract introuvable. Installe-le d'abord.
        goto erreur
    )
)

echo === 3/3 Creation de l'exe ===
python -m PyInstaller --noconfirm --noconsole --name FixItUpAlerte --collect-all customtkinter --add-data "Tesseract-OCR;Tesseract-OCR" fixitup_alert.py
if errorlevel 1 goto erreur

echo.
echo TERMINE : dist\FixItUpAlerte\FixItUpAlerte.exe
pause
exit /b 0

:erreur
echo.
echo ERREUR. Regarde le message ci-dessus.
pause
exit /b 1
