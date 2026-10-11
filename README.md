# Fix It Up – Rare Car Alert

A small Windows tool that watches the chat of the Roblox game **Fix It Up** and alerts you (popup + alarm) when a rare car spawns at the junkyard.

It only reads your screen (screen capture + OCR). It does not touch the game.

## Download

Go to the **Releases** tab of this repository, download `FixItUpAlerte_Setup.exe` and run it.

> Windows may show "Windows protected your PC" (the app is not code-signed).
> Click **More info**, then **Run anyway**.
 virutotal : https://www.virustotal.com/gui/file/ce92111e57ea8ec2664f8355fe25c7094a42ebb3677c2972650846e10d40f8ad/detection
> 
## Usage

1. Run Roblox in **windowed** or **borderless fullscreen** mode.
2. Click **Sélectionner la zone** (select area) and draw a rectangle over the chat.
3. Set the slider: the alert triggers when the rarity is **lower than or equal to** the chosen percentage (from 10% down to 0.001%).
4. Click **Lancer** (start). To stop, click **Éteindre** (turn off).
5. When a matching car spawns: a popup shows the car name and percentage, the alarm loops, and you can close it with the **Fermer** button (or Esc / Enter).

The **Tester l'alarme** button lets you check the sound and the popup. The box at the bottom shows the history of detected cars. The **Voir le texte lu** button shows what the app reads on your screen, which is useful if the reading does not work well.

## Changing the alarm sound

- Put a file whose name starts with **alarme** (`alarme.wav` or `alarme.mp3`) in the app folder, next to `FixItUpAlerte.exe`. It plays in a loop until the popup is closed.
- The app displays under the **Tester l'alarme** button which sound it is using, or why it could not play it.
- Without a file, the app plays beeps. You can adjust them with `ALARM_BEEPS` at the top of `fixitup_alert.py`.
- Volume: `ALARM_VOLUME` (0 to 100). Windows sound: `ALARM_FILE = r"C:\Windows\Media\Alarm05.wav"`.

## Run from source

Requirements: Python 3.11 or 3.12 and [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).

```
pip install -r requirements.txt
python fixitup_alert.py
```

## Build the exe yourself

1. Install Python, Tesseract and [Inno Setup](https://jrsoftware.org/isdl.php).
2. Run `build.bat`: it creates `dist\FixItUpAlerte\FixItUpAlerte.exe`.
3. Open `installer.iss` in Inno Setup and compile (Ctrl+F9): the installer is created in `installer_output`.

## Licenses

Uses [Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache 2.0), customtkinter, mss, OpenCV and numpy.

This project is not affiliated with Roblox or the creators of Fix It Up.
