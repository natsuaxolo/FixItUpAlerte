@echo off
cd /d "%~dp0"

echo === 1/4 Installation des bibliotheques ===
python -m pip install customtkinter mss opencv-python numpy pytesseract pillow pyinstaller
if errorlevel 1 goto erreur

echo === 2/4 Copie de Tesseract (si absent du dossier) ===
if not exist "Tesseract-OCR\tesseract.exe" (
    if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
        xcopy "C:\Program Files\Tesseract-OCR" "Tesseract-OCR\" /E /I /Y
    ) else (
        echo Tesseract introuvable. Installe-le d'abord.
        goto erreur
    )
)

echo === 3/4 Logo ===
if not exist logo.png (
    echo logo.png introuvable. Mets-le dans ce dossier.
    goto erreur
)
python make_icon.py
if errorlevel 1 goto erreur

echo === 4/4 Creation de l'exe ===
python -m PyInstaller --noconfirm --noconsole --name FixItUpAlerte --icon logo.ico --collect-all customtkinter --add-data "Tesseract-OCR;Tesseract-OCR" --add-data "logo.ico;." --add-data "logo.png;." fixitup_alert.py
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
