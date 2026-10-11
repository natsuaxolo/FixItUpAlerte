# Fix It Up – Rare car alert

Small Windows software that monitors the chat of the game Roblox **Fix It Up** and warns you (popup + alarm) when a rare car spawns at the junkyard.

It only reads the screen (capture + OCR). He doesn't touch the game.

## Download

Go to the **Releases** tab of this repository and download `FixItUpAlerte_Setup.exe`, then launch it.

> Windows can display "Windows has protected your computer" (the application is not signed).

> Click on **Additional information**, then **Run anyway**.

## Use

1. Launch Roblox in **windowed** or **full screen window**.

2. Click on **Select area** and draw a rectangle on the chat.

3. Adjust the cursor: the alert is triggered if the rarity is **less than or equal to** the chosen percentage (from 10% to 0.001%).

4. Click on **Launch**. To stop, click on **Turn off**.

5. When a car matches: popup with the name and percentage, loop alarm, **Close** button (or Escape / Enter).

The **Test alarm** button allows you to check the sound and popup. The bottom area displays the history of detected cars. The **See text read** button shows what the app reads on the screen, handy if playback doesn't work well.

## Change the alarm sound

- Drops a file whose name begins with **alarm** (`alarme.wav` or `alarme.mp3`) in the app folder, next to `FixItUpAlerte.exe`. It is played in a loop until the pop-up is closed.

- The app indicates under the button **Test the alarm** what sound it uses, or why it could not read it.

- Without a file, the app plays beeps. They are settled with `ALARM_BEEPS` at the top of `fixitup_alert.py`.

- Volume: `ALARM_VOLUME` (0 to 100). Windows Sound: `ALARM_FILE = r"C:\Windows\Media\Alarm05.wav"`.

## Launch from the source code

3. Open `installer.iss` in Inno Setup and compile (Ctrl+F9): the installer is created in `installer_output`.

## Licences

use [Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache 2.0), customtkinter, mss, OpenCV et numpy.

Project not affiliated with Roblox or the creators of Fix It Up.
