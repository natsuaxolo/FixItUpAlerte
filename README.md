# Fix It Up – Rare Car Alert

🇬🇧 English · 🇫🇷 [Français plus bas](#français)

A small Windows tool that watches the chat of the Roblox game **Fix It Up** and alerts you (popup + alarm) when a rare car spawns at the junkyard.

It reads your screen (screen capture + OCR). The only thing it can send to the game is the optional **Anti-AFK** button (see below).

## Download

Go to the **Releases** tab of this repository, download `FixItUpAlerte_Setup.exe` and run it. Nothing else to install.

> Windows may show "Windows protected your PC" (the app is not code-signed).
> Click **More info**, then **Run anyway**.

## Usage

1. Run Roblox in **windowed** or **borderless fullscreen** mode.
2. Click **Select the area** and draw a rectangle over the chat.
3. Choose a detection method (one at a time):
   - **Percentage method**: the alert triggers when the rarity is **lower than or equal to** the slider value (10% down to 0.001%).
   - **Chosen cars method**: use the search bar (name or percentage) to find cars in the list, which is sorted by spawn chance (the button next to the bar reverses the order). Select one or several cars and click **Add selection** (or double-click a car). You get an alert whenever one of them spawns, whatever its percentage.
4. Click **Start**. To stop, click **Stop**.
5. When a car matches: a popup shows the car name and percentage, the alarm loops, and you close it with the **Close** button (or Esc / Enter).

A message that was already read never triggers a second alert, even when the chat fades out and shows up again.

The flags at the top switch the language (French / English). The **Test the alarm** button checks the sound and the popup. The box at the bottom shows the detection history; the **Show text read** button shows what the app reads on your screen, useful if the reading does not work well.

## Anti-AFK

The **Anti-AFK** switch sends a tiny mouse movement (2 pixels, then back) to the Roblox window every 5 minutes, to avoid the idle kick. If Roblox is not the active window, it is brought to the front for a moment, then your previous window is restored. If you are already playing, nothing is sent.

> ⚠️ This simulates input in your game. Roblox or the game may frown on macros: use it at your own risk. It never buys, drives or clicks anything. It is off by default.

## Car list

The drop-down list contains the **100 cars that spawn at the junkyard**, taken from the game wiki (October 2026), with their spawn chance. If the game adds or changes cars, you can fix or complete the list **without rebuilding**: create a `cars.txt` file next to the app, one car per line, written as in the game chat:

```
Avyra TT;6
Some New Car;0.25
```

## Changing the alarm sound

- Put a file whose name starts with **alarme** (`alarme.wav` or `alarme.mp3`) in the app folder, next to `FixItUpAlerte.exe`. It plays in a loop until the popup is closed.
- The app shows under the **Test the alarm** button which sound it uses, or why it could not play it.
- Without a file, the app plays beeps (`ALARM_BEEPS` at the top of `fixitup_alert.py`). Volume: `ALARM_VOLUME` (0 to 100).

## Custom logo

Replace `logo.png` (any image) before running `build.bat`: it builds the app icon from it.

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

Uses [Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache 2.0), customtkinter, mss, OpenCV, numpy and Pillow.

This project is not affiliated with Roblox or the creators of Fix It Up.

---

# Français

Petit logiciel Windows qui surveille le chat du jeu Roblox **Fix It Up** et te prévient (popup + alarme) quand une voiture rare spawn au junkyard.

Il lit ton écran (capture + OCR). La seule chose qu'il peut envoyer au jeu est le bouton optionnel **Anti-AFK** (voir plus bas).

## Téléchargement

Va dans l'onglet **Releases** de ce dépôt, télécharge `FixItUpAlerte_Setup.exe` et lance-le. Rien d'autre à installer.

> Windows peut afficher « Windows a protégé votre ordinateur » (l'application n'est pas signée).
> Clique sur **Informations complémentaires**, puis **Exécuter quand même**.

## Utilisation

1. Lance Roblox en **fenêtré** ou **plein écran fenêtré**.
2. Clique sur **Sélectionner la zone** et dessine un rectangle sur le chat.
3. Choisis une méthode de détection (une seule à la fois) :
   - **Méthode pourcentage** : l'alerte se déclenche si la rareté est **inférieure ou égale** à la valeur du curseur (de 10 % à 0,001 %).
   - **Méthode voitures choisies** : utilise la barre de recherche (nom ou pourcentage) pour trouver des voitures dans la liste, triée par pourcentage de spawn (le bouton à côté de la barre inverse l'ordre). Sélectionne une ou plusieurs voitures puis clique sur **Ajouter la sélection** (ou double-clique sur une voiture). Tu es alerté dès que l'une d'elles spawn, quel que soit son pourcentage.
4. Clique sur **Lancer**. Pour arrêter, clique sur **Éteindre**.
5. Quand une voiture correspond : popup avec le nom et le pourcentage, alarme en boucle, bouton **Fermer** (ou Échap / Entrée).

Un message déjà lu ne déclenche jamais une deuxième alerte, même quand le chat disparaît puis réapparaît.

Les drapeaux en haut changent la langue (français / anglais). Le bouton **Tester l'alarme** vérifie le son et le popup. La zone du bas affiche l'historique des détections ; le bouton **Voir le texte lu** montre ce que l'appli lit à l'écran, pratique si la lecture ne fonctionne pas bien.

## Anti-AFK

L'interrupteur **Anti-AFK** envoie un tout petit mouvement de souris (2 pixels, puis retour) à la fenêtre Roblox toutes les 5 minutes, pour éviter le kick d'inactivité. Si Roblox n'est pas la fenêtre active, elle passe brièvement au premier plan, puis ta fenêtre précédente est restaurée. Si tu joues déjà, rien n'est envoyé.

> ⚠️ Cela simule une action dans ton jeu. Roblox ou le jeu peuvent mal voir les macros : à utiliser à tes risques. Il n'achète, ne conduit et ne clique sur rien. Il est désactivé par défaut.

## Liste des voitures

Le menu déroulant contient les **100 voitures qui spawn au junkyard**, d'après le wiki du jeu (octobre 2026), avec leur pourcentage. Si le jeu ajoute ou modifie des voitures, tu peux corriger ou compléter la liste **sans recompiler** : crée un fichier `cars.txt` à côté de l'appli, une voiture par ligne, écrite comme dans le chat du jeu :

```
Avyra TT;6
Une Nouvelle Voiture;0,25
```

## Changer le son de l'alarme

- Dépose un fichier dont le nom commence par **alarme** (`alarme.wav` ou `alarme.mp3`) dans le dossier de l'appli, à côté de `FixItUpAlerte.exe`. Il est joué en boucle jusqu'à la fermeture du popup.
- L'appli indique sous le bouton **Tester l'alarme** quel son elle utilise, ou pourquoi elle n'a pas pu le lire.
- Sans fichier, l'appli joue des bips (`ALARM_BEEPS` en haut de `fixitup_alert.py`). Volume : `ALARM_VOLUME` (0 à 100).

## Logo personnalisé

Remplace `logo.png` (n'importe quelle image) avant de lancer `build.bat` : il en fabrique l'icône de l'appli.

## Lancer depuis le code source

Prérequis : Python 3.11 ou 3.12 et [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki).

```
pip install -r requirements.txt
python fixitup_alert.py
```

## Créer l'exe soi-même

1. Installe Python, Tesseract et [Inno Setup](https://jrsoftware.org/isdl.php).
2. Lance `build.bat` : il crée `dist\FixItUpAlerte\FixItUpAlerte.exe`.
3. Ouvre `installer.iss` dans Inno Setup et compile (Ctrl+F9) : l'installeur est créé dans `installer_output`.

## Licences

Utilise [Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache 2.0), customtkinter, mss, OpenCV, numpy et Pillow.

virustotal : https://www.virustotal.com/gui/file/443b046eee612c6afe7adf327de10815338fd2f53cee46cbff20aac2f41bec8a?nocache=1

Projet non affilié à Roblox ni aux créateurs de Fix It Up.
