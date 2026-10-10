# Fix It Up – Alerte voiture rare

Petit logiciel Windows qui surveille le chat du jeu Roblox **Fix It Up** et te prévient (popup + alarme) quand une voiture rare spawn au junkyard.

Il lit uniquement l'écran (capture + OCR). Il ne touche pas au jeu.

## Téléchargement

Va dans l'onglet **Releases** de ce dépôt et télécharge `FixItUpAlerte_Setup.exe`, puis lance-le.

> Windows peut afficher « Windows a protégé votre ordinateur » (l'application n'est pas signée).
> Clique sur **Informations complémentaires**, puis **Exécuter quand même**.

## Utilisation

1. Lance Roblox en **fenêtré** ou **plein écran fenêtré**.
2. Clique sur **Sélectionner la zone** et dessine un rectangle sur le chat.
3. Règle le curseur : l'alerte se déclenche si la rareté est **inférieure ou égale** au pourcentage choisi (de 10 % à 0,001 %).
4. Clique sur **Lancer**. Pour arrêter, clique sur **Éteindre**.
5. Quand une voiture correspond : popup avec le nom et le pourcentage, alarme en boucle, bouton **Fermer** (ou Échap / Entrée).

Le bouton **Tester l'alarme** permet de vérifier le son et le popup. La zone du bas affiche l'historique des voitures détectées. Le bouton **Voir le texte lu** montre ce que l'appli lit à l'écran, pratique si la lecture ne fonctionne pas bien.

## Changer le son de l'alarme

- Dépose un fichier dont le nom commence par **alarme** (`alarme.wav` ou `alarme.mp3`) dans le dossier de l'appli, à côté de `FixItUpAlerte.exe`. Il est joué en boucle jusqu'à la fermeture du popup.
- L'appli indique sous le bouton **Tester l'alarme** quel son elle utilise, ou pourquoi elle n'a pas pu le lire.
- Sans fichier, l'appli joue des bips. Ils se règlent avec `ALARM_BEEPS` en haut de `fixitup_alert.py`.
- Volume : `ALARM_VOLUME` (0 à 100). Son Windows : `ALARM_FILE = r"C:\Windows\Media\Alarm05.wav"`.

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

Utilise [Tesseract](https://github.com/tesseract-ocr/tesseract) (Apache 2.0), customtkinter, mss, OpenCV et numpy.

Projet non affilié à Roblox ni aux créateurs de Fix It Up.
