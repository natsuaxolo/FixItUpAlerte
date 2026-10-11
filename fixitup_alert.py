"""
Fix It Up - Alerte voiture rare / Rare car alert  (v1.5)

Lit le chat Roblox (zone choisie) par OCR et détecte les messages de la forme :
    [System] A rare car has appeared! <Nom de la voiture> — Chance: 4%
Deux méthodes d'alerte : par pourcentage (curseur) ou par voitures choisies.
Un message déjà lu ne déclenche plus jamais d'alerte.
"""
import collections
import ctypes
import difflib
import json
import os
import queue
import re
import sys
import threading
import time
import tkinter as tk

# --- DPI : doit être fait AVANT de créer les fenêtres, pour que les
# --- coordonnées de la zone correspondent aux vrais pixels de l'écran
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import cv2
import customtkinter as ctk
import mss
import numpy as np
import pytesseract
import winsound
from PIL import Image, ImageDraw


def resource_path(rel: str) -> str:
    """Chemin d'un fichier embarqué (marche en .py et en .exe PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# Dossier où se trouve l'appli (là où tu déposes ton fichier alarme / cars.txt)
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
#                          RÉGLAGES MODIFIABLES
# =====================================================================
SCAN_DELAY = 0.3            # secondes entre deux lectures du chat
SYSTEM_PREFIX = "system"    # mot entre crochets au début du message

# --- ALARME -----------------------------------------------------------
# Dépose un fichier dont le nom commence par "alarme" à côté de l'appli :
#   alarme.wav  ou  alarme.mp3  (ou .wma / .m4a)
# Ou indique ici un chemin complet (laisse "" pour désactiver), par exemple :
#   ALARM_FILE = r"C:\Windows\Media\Alarm05.wav"
ALARM_FILE = ""
ALARM_VOLUME = 100          # volume de 0 à 100
# Si aucun fichier n'est trouvé : des bips (fréquence en Hz, durée en ms)
ALARM_BEEPS = [(1400, 180), (900, 180)]

# --- ANTI-AFK ---------------------------------------------------------
AFK_INTERVAL_MIN = 5        # envoi d'un petit mouvement de souris toutes les X minutes
AFK_ACTIVE_IDLE = 120       # si tu joues déjà dans Roblox (< X secondes d'inactivité), rien n'est envoyé
# =====================================================================

# Tesseract : 1) embarqué avec l'appli, 2) sinon installé sur le PC
TESS_BUNDLED = resource_path(os.path.join("Tesseract-OCR", "tesseract.exe"))
TESS_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESS_BUNDLED):
    pytesseract.pytesseract.tesseract_cmd = TESS_BUNDLED
    os.environ["TESSDATA_PREFIX"] = resource_path(os.path.join("Tesseract-OCR", "tessdata"))
elif os.path.exists(TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESS_PATH

CONFIG_FILE = os.path.expanduser("~/.fixitup_alert.json")

# Une voiture déjà alertée est "oubliée" seulement si elle reste absente du chat
# pendant ce temps (secondes de chat visible) : elle a alors vraiment disparu
# du chat, et un nouveau spawn identique sera de nouveau signalé.
FORGET_AFTER = 90
# ligne de chat classique : "[System] ..." ou "Pseudo: message"
CHAT_LINE_RE = re.compile(r"^\s*(?:\[[^\]]{3,10}\]|[\w.\-]{3,20}\s*:)\s*\S", re.M)

# "[System] ...texte... Chance: 4%"  (tolère les petites erreurs d'OCR et les
# retours à la ligne du chat). Le texte du milieu ne contient jamais de crochet.
CAR_RE = re.compile(
    r"[\[\(\{|]?\s*(?P<tag>[A-Za-z]{4,8})\s*[\]\)\}|Il1]?\s*"
    r"(?P<body>[^\[\]]*?)"
    r"Chan\w{0,3}\s*[:;.]?\s*(?P<pct>\d+(?:[.,]\d+)?)\s*%",
    re.I | re.S,
)

# =====================================================================
#                         LISTE DES VOITURES
# =====================================================================
# Voitures du junkyard (nom ; % de spawn), d'après le wiki du jeu
# (fix-it-up.fandom.com/wiki/Cars, octobre 2026) : seules les voitures qui
# apparaissent au junkyard sont listées (pas les voitures d'enchères, de
# boutique, d'événement ou retirées de la vente).
# Le jeu peut ajouter ou modifier des voitures. Pour corriger / compléter la
# liste SANS recompiler : crée un fichier  cars.txt  à côté de l'appli, une
# voiture par ligne, au format   Nom de la voiture;pourcentage   (ex :  Avyra TT;6 ).
# Les lignes du fichier remplacent / complètent cette liste.
# Le nom doit être écrit comme dans le chat du jeu.
DEFAULT_CARS = [
    ("Avyra RF3", 0.6), ("Avyra TT", 6), ("Avyra V4", 15), ("Avyra V5", 1), ("Avyra V8", 0.4),
    ("Chule Camarao", 1), ("Chule Camarao 1979 Sport", 3), ("Chule Camarao IRON-F 1990", 6),
    ("Chule Curgete", 0.1), ("DOGO Carrega", 0.02), ("DOGO Carrega FEP Hellgato", 0.05),
    ("Fia-Te 10026p", 0.2), ("Fia-Te 131", 1.2), ("Fia-Te Alberto 300", 3),
    ("Fia-Te Ponto", 50), ("Fia-Te X1-9", 10), ("Fotos Exigente Cura", 2),
    ("Four Mustank Relby SP500", 0.2), ("Four Party", 6), ("Four Que", 45), ("Four Rex", 1),
    ("Four Traffic", 6), ("Four Transito Mk.6", 18), ("Ganley Continente FP", 3),
    ("Hay Semente", 22), ("Holde Civico Si", 8), ("Holde Ciwiq", 11),
    ("Holde Ciwiq Pyte F EK", 7), ("Holde Feat", 16), ("Holde Inteiro", 7),
    ("Holde Proluiz", 0.8), ("Holde TipeRar", 0.5), ("Hyonda i20N", 7),
    ("Lanca Status FR4", 0.2), ("Leskus FP 50", 0.05), ("Leskus not200", 10),
    ("Lester Moniz DB11", 0.35), ("Lion JF-S", 7), ("Lokswag Arteao R", 3),
    ("Lokswag Brasiuiu", 0.3), ("Lokswag Cissoko F", 4), ("Lokswag Golo", 30),
    ("Lokswag Golo GT", 2), ("Lokswag Golo MK4", 15), ("Lokswag Golo MK5", 7),
    ("Lokswag Nype 1", 20), ("Lokswag Passar", 20), ("Lokswag Tourette", 6),
    ("Mamibac Escalada EFV", 0.5), ("Mamibac FZ5-B", 2), ("Mata Piada", 0.01),
    ("Matsu Elipz FZX", 12), ("Matsu Lanca", 2), ("Matsu Lanca Evolucao", 4),
    ("Merquis 190F EVOLUCAO II", 3), ("Merquis 560 SEC Koenig", 0.15), ("Merquis C203", 7),
    ("Merquis F55", 0.3), ("Merquis Maibac S650", 0.25), ("Merquis SLX", 0.05),
    ("Merquis Z73", 1), ("Mine Copa S", 0.05), ("Missah 400X", 2),
    ("Missah Groundline 2000 GT-R", 0.3), ("Ontel Astron", 4), ("Ontel Costa", 30),
    ("Ontel Kadeto", 24), ("Ontel Pontus Neta", 20), ("Peujo 200e5", 25), ("Peujo 200e6", 50),
    ("Peujo 258 F5", 13), ("Peujo 400e6", 20), ("Peujo FO6 HyperCopa L1600", 12),
    ("Porx Bareira RF", 0.3), ("Raguer XisR", 5), ("Ratos Rotos Esporte", 0.5),
    ("Renas 5 Turbo", 0.8), ("Renas Fio III RF", 25), ("Renas Kapturado", 30),
    ("Renas Mugano", 5), ("Renas Suino", 25), ("Sabes Muito", 40), ("Sacode Oitava", 20),
    ("Siath Lion", 50), ("Sigma Roma Broeiro", 7), ("Skami Truk", 0.05), ("Toyoda AFF67", 0.3),
    ("Toyoda Camri", 6), ("Toyoda Hellox", 7), ("Toyoda Perseguidor JFX100", 12),
    ("Toyoda Yapp", 2), ("Vemca K3 E", 10), ("Vemca K3 e92", 1), ("Vemca K3 F", 0.02),
    ("Vemca K5 E", 0.5), ("Vemca K5 e39", 3), ("Vemca K8", 0.05), ("Vovo F60 Polo", 2.5),
    ("Vovo Sr60", 17), ("Xitro J3", 40),
]

# =====================================================================
#                              TEXTES FR / EN
# =====================================================================
TEXTS = {
    "fr": {
        "window": "Fix It Up - Alerte",
        "title": "Alerte voiture rare",
        "alert_if": "Alerter si rareté ≤",
        "m_pct": "Méthode pourcentage (curseur)",
        "m_cars": "Méthode voitures choisies",
        "cars_search": "Rechercher une voiture :",
        "search_ph": "Tape un nom ou un pourcentage…",
        "sort_rare": "Tri : plus rare d'abord ▲",
        "sort_common": "Tri : plus courant d'abord ▼",
        "no_results": "Aucun résultat",
        "add": "Ajouter la sélection",
        "cars_box": "Voitures à surveiller :",
        "no_cars": "Aucune voiture ajoutée",
        "select_zone": "Sélectionner la zone",
        "zone_none": "Aucune zone sélectionnée",
        "zone_size": "Zone : {w}x{h} px",
        "start": "Lancer",
        "stop": "Éteindre",
        "test": "Tester l'alarme",
        "snd_file": "Son : {f}",
        "snd_err": "Son : {e} → bips utilisés",
        "snd_none": "Son : bips (aucun fichier « alarme » trouvé dans {d})",
        "st_stopped": "Arrêté",
        "st_running": "Surveillance en cours… (messages voiture lus : {n})",
        "st_zone": "Sélectionne d'abord une zone",
        "st_cars": "Ajoute au moins une voiture à la liste",
        "afk": "Anti-AFK",
        "afk_off": "Anti-AFK désactivé",
        "afk_wait": "Actif : petit mouvement de souris toutes les {m} min",
        "afk_sent": "Actif : dernier envoi à {t}",
        "afk_active": "Actif : tu joues déjà ({t}), rien envoyé",
        "afk_none": "Actif : fenêtre Roblox introuvable ({t})",
        "log_hist": "Historique des détections :",
        "log_raw": "Texte lu sur l'écran (debug) :",
        "btn_raw": "Voir le texte lu (debug)",
        "btn_hist": "Voir l'historique",
        "empty_hist": "(rien détecté pour l'instant)",
        "empty_raw": "(aucun texte détecté)",
        "ev_base": "{n} voiture(s) déjà dans le chat : ignorée(s)",
        "ev_alert": "{name} — {pct} %  → ALERTE",
        "ev_ign_pct": "{name} — {pct} %  (au-dessus du seuil)",
        "ev_ign_list": "{name} — {pct} %  (pas dans ta liste)",
        "popup_title": "🚗 VOITURE RARE !",
        "popup_close": "FERMER (Échap)",
        "sel_hint": "Dessine un rectangle sur le chat  (Échap = annuler)",
        "err_tess": "Tesseract introuvable. Installe-le (voir étapes).",
        "err_read": "Erreur lecture : {e}",
        "err_gen": "Erreur : {e}",
        "test_car": "Voiture test",
    },
    "en": {
        "window": "Fix It Up - Alert",
        "title": "Rare car alert",
        "alert_if": "Alert if rarity ≤",
        "m_pct": "Percentage method (slider)",
        "m_cars": "Chosen cars method",
        "cars_search": "Search a car:",
        "search_ph": "Type a name or a percentage…",
        "sort_rare": "Sort: rarest first ▲",
        "sort_common": "Sort: most common first ▼",
        "no_results": "No result",
        "add": "Add selection",
        "cars_box": "Cars to watch:",
        "no_cars": "No car added yet",
        "select_zone": "Select the area",
        "zone_none": "No area selected",
        "zone_size": "Area: {w}x{h} px",
        "start": "Start",
        "stop": "Stop",
        "test": "Test the alarm",
        "snd_file": "Sound: {f}",
        "snd_err": "Sound: {e} → beeps used",
        "snd_none": "Sound: beeps (no \"alarme\" file found in {d})",
        "st_stopped": "Stopped",
        "st_running": "Watching… (car messages read: {n})",
        "st_zone": "Select an area first",
        "st_cars": "Add at least one car to the list",
        "afk": "Anti-AFK",
        "afk_off": "Anti-AFK off",
        "afk_wait": "On: small mouse move every {m} min",
        "afk_sent": "On: last sent at {t}",
        "afk_active": "On: you are already playing ({t}), nothing sent",
        "afk_none": "On: Roblox window not found ({t})",
        "log_hist": "Detection history:",
        "log_raw": "Text read on screen (debug):",
        "btn_raw": "Show text read (debug)",
        "btn_hist": "Show history",
        "empty_hist": "(nothing detected yet)",
        "empty_raw": "(no text detected)",
        "ev_base": "{n} car(s) already in the chat: ignored",
        "ev_alert": "{name} — {pct} %  → ALERT",
        "ev_ign_pct": "{name} — {pct} %  (above the threshold)",
        "ev_ign_list": "{name} — {pct} %  (not in your list)",
        "popup_title": "🚗 RARE CAR!",
        "popup_close": "CLOSE (Esc)",
        "sel_hint": "Draw a rectangle over the chat  (Esc = cancel)",
        "err_tess": "Tesseract not found. Install it (see steps).",
        "err_read": "Read error: {e}",
        "err_gen": "Error: {e}",
        "test_car": "Test car",
    },
}
LANG = "fr"


def t(key: str, **kw) -> str:
    s = TEXTS.get(LANG, TEXTS["fr"]).get(key) or TEXTS["fr"].get(key, key)
    return s.format(**kw) if kw else s


def system_lang() -> str:
    try:
        return "fr" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x0C else "en"
    except Exception:
        return "fr"


def make_flag(code: str, w: int = 60, h: int = 40):
    """Dessine un drapeau (les emojis drapeaux ne s'affichent pas sous Windows)."""
    S = 4
    W, H = w * S, h * S
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    if code == "fr":
        d.rectangle([0, 0, W // 3, H], fill=(0, 85, 164))
        d.rectangle([2 * W // 3, 0, W, H], fill=(239, 65, 53))
    else:
        red = (200, 16, 46)
        d.rectangle([0, 0, W, H], fill=(1, 33, 105))
        for a, b in (((0, 0), (W, H)), ((0, H), (W, 0))):
            d.line([a, b], fill="white", width=int(H * 0.22))
            d.line([a, b], fill=red, width=int(H * 0.08))
        d.rectangle([W // 2 - int(H * 0.18), 0, W // 2 + int(H * 0.18), H], fill="white")
        d.rectangle([0, H // 2 - int(H * 0.18), W, H // 2 + int(H * 0.18)], fill="white")
        d.rectangle([W // 2 - int(H * 0.1), 0, W // 2 + int(H * 0.1), H], fill=red)
        d.rectangle([0, H // 2 - int(H * 0.1), W, H // 2 + int(H * 0.1)], fill=red)
    resample = getattr(Image, "Resampling", Image).LANCZOS
    return img.resize((w, h), resample)


def make_logo(size: int = 256):
    """Logo de l'appli : une voiture jaune avec une pastille d'alerte rouge."""
    S = 4
    W = 512 * S
    k = W / 512.0
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def box(x0, y0, x1, y1):
        return [x0 * k, y0 * k, x1 * k, y1 * k]

    d.rounded_rectangle(box(8, 8, 504, 504), radius=int(100 * k), fill=(18, 33, 61, 255))
    # carrosserie + habitacle
    d.rounded_rectangle(box(70, 280, 442, 362), radius=int(30 * k), fill=(255, 196, 0, 255))
    d.polygon([(140 * k, 284 * k), (190 * k, 214 * k), (330 * k, 214 * k), (388 * k, 284 * k)],
              fill=(255, 196, 0, 255))
    # vitres
    d.polygon([(166 * k, 276 * k), (204 * k, 228 * k), (252 * k, 228 * k), (252 * k, 276 * k)],
              fill=(150, 195, 230, 255))
    d.polygon([(266 * k, 228 * k), (322 * k, 228 * k), (362 * k, 276 * k), (266 * k, 276 * k)],
              fill=(150, 195, 230, 255))
    # roues
    for cx in (156, 356):
        d.ellipse(box(cx - 44, 322, cx + 44, 410), fill=(20, 20, 24, 255))
        d.ellipse(box(cx - 20, 346, cx + 20, 386), fill=(190, 190, 195, 255))
    # pastille d'alerte
    d.ellipse(box(330, 40, 490, 200), fill=(255, 255, 255, 255))
    d.ellipse(box(340, 50, 480, 190), fill=(220, 50, 47, 255))
    d.rounded_rectangle(box(402, 76, 418, 138), radius=int(8 * k), fill=(255, 255, 255, 255))
    d.ellipse(box(400, 148, 420, 168), fill=(255, 255, 255, 255))
    resample = getattr(Image, "Resampling", Image).LANCZOS
    return img.resize((size, size), resample)


def load_logo_image():
    """logo.png s'il existe à côté de l'appli, sinon le logo dessiné par défaut."""
    p = find_data_file("logo.png")
    if p:
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            pass
    return make_logo(256)


# ----------------------------------------------------------------- utilitaires
def slider_to_pct(s: float) -> float:
    """0..1 -> 10% .. 0.001% (échelle logarithmique)."""
    return 10 ** (1 - 4 * s)


def pct_to_slider(p: float) -> float:
    return (1 - np.log10(p)) / 4


def fmt_pct(p: float) -> str:
    return f"{p:.3f}".rstrip("0").rstrip(".")


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def same_name(a: str, b: str) -> bool:
    """Deux clés de noms de voiture désignent-elles la même voiture ?
    (tolère une petite erreur d'OCR, mais jamais un chiffre différent)"""
    if a == b:
        return True
    return (re.sub(r"\D", "", a) == re.sub(r"\D", "", b)
            and abs(len(a) - len(b)) <= 1
            and difflib.SequenceMatcher(None, a, b).ratio() >= 0.88)


def name_selected(name: str, selected_keys) -> bool:
    k = norm_key(name)
    return any(same_name(k, s) for s in selected_keys)


def find_data_file(filename: str):
    embedded = getattr(sys, "_MEIPASS", APP_DIR)
    for folder in dict.fromkeys([APP_DIR, os.getcwd(), embedded]):
        p = os.path.join(folder, filename)
        if os.path.isfile(p):
            return p
    return None


def load_cars() -> dict:
    """Liste des voitures {nom: pourcentage ou None} : liste de départ + cars.txt."""
    cars = dict(DEFAULT_CARS)
    p = find_data_file("cars.txt")
    if p:
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    name, _, pct = line.rpartition(";")
                    if not name:
                        name, pct = line, ""
                    name = name.strip()
                    try:
                        val = float(pct.replace("%", "").replace(",", ".").strip())
                    except ValueError:
                        val = None
                    if name:
                        cars[name] = val
        except Exception:
            pass
    return cars


CARS = load_cars()


def car_label(name: str) -> str:
    pct = CARS.get(name)
    return f"{name} ({fmt_pct(pct)} %)" if pct is not None else name


def car_choices(query: str, selected, ascending: bool = True):
    """Voitures proposées dans la liste : filtrées par la recherche (nom ou
    pourcentage), sans celles déjà choisies, triées par pourcentage."""
    q = query.strip().lower()
    chosen = {norm_key(s) for s in selected}
    out = [n for n in CARS
           if norm_key(n) not in chosen and (not q or q in car_label(n).lower())]
    known = [n for n in out if CARS.get(n) is not None]
    unknown = [n for n in out if CARS.get(n) is None]
    if ascending:
        known.sort(key=lambda n: (CARS[n], n.lower()))
    else:
        known.sort(key=lambda n: (-CARS[n], n.lower()))
    return known + sorted(unknown, key=str.lower)


def extract_cars(text: str):
    """Retourne la liste ordonnée des messages [System] ... Chance: X% du texte lu."""
    cars = []
    for m in CAR_RE.finditer(text):
        tag = m.group("tag").lower()
        if difflib.SequenceMatcher(None, tag, SYSTEM_PREFIX.lower()).ratio() < 0.7:
            continue
        try:
            pct = float(m.group("pct").replace(",", "."))
        except ValueError:
            continue
        if not 0 < pct <= 100:
            continue
        body = re.sub(r"\s+", " ", m.group("body"))
        name = re.sub(r"^.*?appear\w*\W*", "", body, count=1, flags=re.I)
        name = re.sub(r"^[^A-Za-z0-9]+|[^A-Za-z0-9]+$", "", name)
        if not name:
            name = body.strip()
        key = norm_key(name)
        if len(key) < 3:
            continue
        cars.append({"name": name, "key": key, "pct": pct, "end": m.end()})
    return cars


# ------------------------------------------------------------------- alarme
last_alarm_error = ""       # affiché dans l'appli pour comprendre un souci de son
_alarm_counter = 0


def find_alarm_file():
    """Cherche le fichier d'alarme (ALARM_FILE, sinon alarme.* à côté de l'appli)."""
    if ALARM_FILE and os.path.isfile(ALARM_FILE):
        return ALARM_FILE
    exts = (".wav", ".mp3", ".wma", ".m4a")
    embedded = getattr(sys, "_MEIPASS", APP_DIR)   # fichier embarqué dans l'exe
    for folder in dict.fromkeys([APP_DIR, os.getcwd(), embedded]):
        try:
            for name in sorted(os.listdir(folder)):
                low = name.lower()
                if low.startswith("alarme") and low.endswith(exts):
                    return os.path.join(folder, name)
        except Exception:
            pass
    return None


def _mci(cmd: str):
    buf = ctypes.create_unicode_buffer(256)
    err = ctypes.windll.winmm.mciSendStringW(cmd, buf, 255, 0)
    if err:
        msg = ctypes.create_unicode_buffer(256)
        ctypes.windll.winmm.mciGetErrorStringW(err, msg, 255)
        return err, msg.value
    return 0, buf.value


class AlarmPlayer:
    """Joue le fichier d'alarme en boucle (MCI de Windows : wav, mp3...),
    ou des bips si aucun fichier n'est utilisable."""

    def __init__(self):
        self.stop_event = threading.Event()
        self.path = find_alarm_file()
        threading.Thread(target=self.run, daemon=True).start()

    def stop(self):
        self.stop_event.set()

    def run(self):
        global last_alarm_error, _alarm_counter
        last_alarm_error = ""
        if self.path:
            _alarm_counter += 1
            alias = f"fixalarm{_alarm_counter}"
            types = ["waveaudio", "mpegvideo"] if self.path.lower().endswith(".wav") else ["mpegvideo"]
            opened, err_msg = False, ""
            for tp in types:
                err, msg = _mci(f'open "{self.path}" type {tp} alias {alias}')
                if not err:
                    opened = True
                    break
                err_msg = msg
            if opened:
                _mci(f"setaudio {alias} volume to {int(max(0, min(100, ALARM_VOLUME)) * 10)}")
                while not self.stop_event.is_set():
                    _mci(f"seek {alias} to start")
                    _mci(f"play {alias}")
                    while not self.stop_event.is_set():
                        _, mode = _mci(f"status {alias} mode")
                        if mode != "playing":
                            break
                        time.sleep(0.05)
                _mci(f"stop {alias}")
                _mci(f"close {alias}")
                return
            last_alarm_error = f"{os.path.basename(self.path)} ({err_msg})"
        # Bips (aucun fichier, ou fichier illisible)
        while not self.stop_event.is_set():
            for freq, dur in ALARM_BEEPS:
                if self.stop_event.is_set():
                    break
                winsound.Beep(freq, dur)


def sound_status_text() -> str:
    p = find_alarm_file()
    if last_alarm_error:
        return t("snd_err", e=last_alarm_error)
    if p:
        return t("snd_file", f=os.path.basename(p))
    return t("snd_none", d=APP_DIR)


# ------------------------------------------------------------------- anti-AFK
_user32 = None


def user32():
    global _user32
    if _user32 is None:
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p
        for fn in ("SetForegroundWindow", "IsWindow", "IsIconic", "IsWindowVisible",
                   "GetWindowTextLengthW", "BringWindowToTop"):
            getattr(u, fn).argtypes = [ctypes.c_void_p]
        u.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        u.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
        u.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        _user32 = u
    return _user32


def find_roblox_window():
    u = user32()
    found = []
    enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd):
            n = u.GetWindowTextLengthW(hwnd)
            if n:
                buf = ctypes.create_unicode_buffer(n + 1)
                u.GetWindowTextW(hwnd, buf, n + 1)
                if buf.value.strip().lower() == "roblox":
                    found.append(hwnd)
        return True

    u.EnumWindows(enum_proc(cb), 0)
    return found[0] if found else None


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def idle_seconds() -> float:
    lii = _LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(lii)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
    return ((ctypes.windll.kernel32.GetTickCount() - lii.dwTime) & 0xFFFFFFFF) / 1000.0


def _focus(hwnd, from_hwnd):
    """Met une fenêtre au premier plan (astuce AttachThreadInput pour que
    Windows l'autorise)."""
    u = user32()
    k = ctypes.windll.kernel32
    my_thread = k.GetCurrentThreadId()
    fg_thread = u.GetWindowThreadProcessId(from_hwnd, None) if from_hwnd else 0
    if fg_thread:
        u.AttachThreadInput(my_thread, fg_thread, True)
    u.BringWindowToTop(hwnd)
    u.SetForegroundWindow(hwnd)
    if fg_thread:
        u.AttachThreadInput(my_thread, fg_thread, False)


def afk_ping() -> str:
    """Envoie un tout petit mouvement de souris (2 px et retour) à Roblox.
    Retourne "sent", "active" (tu joues déjà) ou "none" (Roblox introuvable)."""
    u = user32()
    hwnd = find_roblox_window()
    if not hwnd:
        return "none"
    prev = u.GetForegroundWindow()
    if prev == hwnd and idle_seconds() < AFK_ACTIVE_IDLE:
        return "active"
    was_minimized = bool(u.IsIconic(hwnd))
    if prev != hwnd:
        if was_minimized:
            u.ShowWindow(hwnd, 9)          # SW_RESTORE
        _focus(hwnd, prev)
        time.sleep(0.4)
    for dx in (2, -2, 2, -2):
        u.mouse_event(0x0001, dx, 0, 0, 0)  # MOUSEEVENTF_MOVE
        time.sleep(0.06)
    time.sleep(0.2)
    if prev and prev != hwnd and u.IsWindow(prev):
        _focus(prev, hwnd)                 # on te rend ta fenêtre
        if was_minimized:
            u.ShowWindow(hwnd, 6)          # SW_MINIMIZE
    return "sent"


class AfkWorker(threading.Thread):
    def __init__(self, out_queue):
        super().__init__(daemon=True)
        self.q = out_queue
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        next_t = time.time() + AFK_INTERVAL_MIN * 60
        while not self.stop_event.wait(1.0):
            if time.time() >= next_t:
                try:
                    status = afk_ping()
                except Exception:
                    status = "none"
                self.q.put(("afk", (status, time.strftime("%H:%M"))))
                next_t = time.time() + AFK_INTERVAL_MIN * 60


# ------------------------------------------------------------- sélecteur de zone
class ZoneSelector:
    def __init__(self, root, on_done):
        self.on_done = on_done
        self.start = None
        self.rect = None
        self.win = tk.Toplevel(root)
        self.win.attributes("-fullscreen", True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.3)
        self.win.configure(bg="black", cursor="crosshair")
        self.canvas = tk.Canvas(self.win, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_text(
            self.win.winfo_screenwidth() // 2, 60,
            text=t("sel_hint"),
            fill="white", font=("Segoe UI", 20, "bold"),
        )
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.win.bind("<Escape>", lambda e: self.win.destroy())
        self.win.focus_force()

    def press(self, e):
        self.start = (e.x_root, e.y_root)
        self.rect = self.canvas.create_rectangle(
            e.x, e.y, e.x, e.y, outline="red", width=3)

    def drag(self, e):
        if self.rect and self.start:
            x0 = self.start[0] - self.win.winfo_rootx()
            y0 = self.start[1] - self.win.winfo_rooty()
            self.canvas.coords(self.rect, x0, y0, e.x, e.y)

    def release(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        x2, y2 = e.x_root, e.y_root
        left, top = min(x1, x2), min(y1, y2)
        w, h = abs(x2 - x1), abs(y2 - y1)
        self.win.destroy()
        if w > 20 and h > 10:
            self.on_done({"left": left, "top": top, "width": w, "height": h})


# --------------------------------------------------------------- thread de lecture
class Watcher(threading.Thread):
    """Lit le chat en boucle. Chaque message voiture est mémorisé : un message
    déjà lu ne déclenche plus jamais d'alerte, même s'il réapparaît (chat qui
    se réaffiche, lecture instable...)."""

    def __init__(self, region, get_rule, out_queue):
        super().__init__(daemon=True)
        self.region = region
        self.get_rule = get_rule   # -> (mode, seuil %, [clés des voitures choisies])
        self.q = out_queue
        self.stop_event = threading.Event()
        self.known = {}            # clé voiture -> {"count", "absent", "pct"} (déjà lues)
        self.pending = {}          # nouvelles voitures en cours de confirmation
        self.notes = []            # infos pour l'historique
        self.baselined = False
        self.started = time.time()
        self.last_tick = self.started

    def stop(self):
        self.stop_event.set()

    @staticmethod
    def read_text(img_bgr) -> str:
        # Luminosité de la couleur la plus forte : tout texte clair (jaune,
        # blanc, etc.) ressort, quelle que soit sa couleur.
        v = np.max(img_bgr, axis=2)
        scale = 3 if v.shape[0] < 450 else 2
        v = cv2.resize(v, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        _, th = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(th) < 127:      # fond sombre + texte clair -> on inverse
            th = cv2.bitwise_not(th)
        return pytesseract.image_to_string(th, config="--psm 6")

    def _canon(self, car):
        """Clé d'une voiture déjà connue qui correspond à celle-ci (lecture OCR
        légèrement différente), sinon sa propre clé."""
        k = car["key"]
        pool = [(key, e["pct"]) for key, e in self.known.items()]
        pool += [(key, p["pcts"][-1]) for key, p in self.pending.items()]
        for key, _ in pool:
            if key == k:
                return k
        digits = re.sub(r"\D", "", k)
        for key, pct in pool:
            if (pct == car["pct"] and re.sub(r"\D", "", key) == digits
                    and difflib.SequenceMatcher(None, key, k).ratio() >= 0.9):
                return key
        return k

    def process(self, text, cars, now):
        """Retourne les voitures réellement NOUVELLES [(nom, %)], confirmées sur
        plusieurs lectures consécutives."""
        dt = min(max(now - self.last_tick, 0.0), 3.0)
        self.last_tick = now
        chat_visible = len(CHAT_LINE_RE.findall(text)) >= 2

        for c in cars:
            c["key"] = self._canon(c)
        cur = collections.Counter(c["key"] for c in cars)
        info = {}
        for c in cars:
            info.setdefault(c["key"], c)

        # Première fois qu'on voit des voitures : ce sont des anciens messages,
        # sauf si le chat vient d'apparaître longtemps après le lancement et
        # que la dernière voiture est le tout dernier message (= nouvelle).
        if cars and not self.baselined:
            self.baselined = True
            last = cars[-1]
            newest_is_new = (now - self.started > 6
                             and not CHAT_LINE_RE.search(text[last["end"]:]))
            old = 0
            for k, n in cur.items():
                cnt = n - (1 if newest_is_new and k == last["key"] else 0)
                if cnt > 0:
                    self.known[k] = {"count": cnt, "absent": 0.0, "pct": info[k]["pct"]}
                    old += cnt
            if old:
                self.notes.append(old)

        # Nouvelles voitures = plus d'exemplaires visibles que de déjà lus
        seen = set()
        for k, n in cur.items():
            have = self.known[k]["count"] if k in self.known else 0
            if n > have:
                seen.add(k)
                p = self.pending.setdefault(k, {"n": 0, "pcts": [], "car": None})
                p["n"] += 1
                p["pcts"].append(info[k]["pct"])
                p["car"] = info[k]
        for k in list(self.pending):
            if k not in seen:
                del self.pending[k]

        # Confirmation : lue au moins 2 fois de suite avec le même pourcentage
        # (évite les erreurs d'OCR quand le chat apparaît / disparaît en fondu).
        out = []
        for k, p in list(self.pending.items()):
            last2 = p["pcts"][-2:]
            if p["n"] >= 2 and (len(set(last2)) == 1 or p["n"] >= 4):
                pct = collections.Counter(p["pcts"]).most_common(1)[0][0]
                e = self.known.setdefault(k, {"count": 0, "absent": 0.0, "pct": pct})
                e["count"] += 1
                e["absent"] = 0.0
                e["pct"] = pct
                out.append((p["car"]["name"], pct))
                del self.pending[k]

        # Oubli : une voiture absente du chat pendant longtemps (chat visible)
        # a vraiment disparu, un futur message identique sera donc nouveau.
        if chat_visible:
            for k, e in list(self.known.items()):
                n = cur.get(k, 0)
                if n >= e["count"]:
                    e["absent"] = 0.0
                else:
                    e["absent"] += dt
                    if e["absent"] >= FORGET_AFTER:
                        if n == 0:
                            del self.known[k]
                        else:
                            e["count"] = n
                            e["absent"] = 0.0
        return out

    def run(self):
        try:
            with mss.mss() as sct:
                while not self.stop_event.is_set():
                    try:
                        shot = np.array(sct.grab(self.region))[:, :, :3]
                        text = self.read_text(np.ascontiguousarray(shot))
                    except pytesseract.TesseractNotFoundError:
                        self.q.put(("error", ("tess", "")))
                        return
                    except Exception as ex:
                        self.q.put(("error", ("read", str(ex))))
                        time.sleep(1)
                        continue

                    self.q.put(("text", text.strip()))
                    cars = extract_cars(text)
                    self.q.put(("count", len(cars)))
                    mode, threshold, selected = self.get_rule()
                    found = self.process(text, cars, time.time())
                    for n in self.notes:
                        self.q.put(("event", (time.strftime("%H:%M:%S"), "base", n, None)))
                    self.notes.clear()
                    for name, pct in found:
                        ts = time.strftime("%H:%M:%S")
                        if mode == "cars":
                            ok, kind = name_selected(name, selected), "ign_list"
                        else:
                            ok, kind = pct <= threshold, "ign_pct"
                        if ok:
                            self.q.put(("event", (ts, "alert", name, pct)))
                            self.q.put(("alert", (name, pct)))
                        else:
                            self.q.put(("event", (ts, kind, name, pct)))
                    time.sleep(SCAN_DELAY)
        except Exception as ex:
            self.q.put(("error", ("gen", str(ex))))


# ----------------------------------------------------------------------- popup
class AlertPopup:
    def __init__(self, root, name, pct):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg="#c0392b")
        w, h = 560, 230
        x = (self.win.winfo_screenwidth() - w) // 2
        self.win.geometry(f"{w}x{h}+{x}+40")

        tk.Label(self.win, text=t("popup_title"), bg="#c0392b", fg="white",
                 font=("Segoe UI", 22, "bold")).pack(pady=(14, 2))
        tk.Label(self.win, text=name, bg="#c0392b", fg="white", wraplength=520,
                 font=("Segoe UI", 18)).pack()
        tk.Label(self.win, text=f"{fmt_pct(pct)} %", bg="#c0392b", fg="#ffe066",
                 font=("Segoe UI", 26, "bold")).pack(pady=2)
        tk.Button(self.win, text=t("popup_close"), command=self.close,
                  font=("Segoe UI", 16, "bold"), bg="white", fg="black",
                  relief="flat", padx=20, pady=6).pack(pady=8)
        self.win.bind("<Escape>", lambda e: self.close())
        self.win.bind("<Return>", lambda e: self.close())
        self.win.lift()
        self.alarm = AlarmPlayer()

    def close(self):
        self.alarm.stop()
        try:
            self.win.destroy()
        except Exception:
            pass


# ------------------------------------------------------------------ application
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        global LANG
        ctk.set_appearance_mode("dark")
        self.attributes("-topmost", True)
        self.geometry("440x900")
        self.minsize(420, 560)

        cfg = load_config()
        LANG = cfg.get("lang") if cfg.get("lang") in TEXTS else system_lang()
        self.region = cfg.get("region")
        self.threshold = cfg.get("threshold", 1.0)
        self.mode = cfg.get("mode") if cfg.get("mode") in ("percent", "cars") else "percent"
        self.selected = [n for n in cfg.get("cars", []) if isinstance(n, str)]

        self.q = queue.Queue()
        self.watcher = None
        self.popup = None
        self.afk_worker = None
        self.afk_last = None            # (statut, heure)
        self.last_text = ""
        self.events = []                # historique des détections
        self.raw_mode = False           # False = historique, True = texte brut lu (debug)
        self.cars_seen = 0
        self.status_state = ("stopped",)
        self.search_text = ""
        self.sort_asc = True            # True = plus rare d'abord
        self.choice_names = []
        self.flags = {c: ctk.CTkImage(make_flag(c), size=(30, 20)) for c in ("fr", "en")}
        self.logo = ctk.CTkImage(load_logo_image(), size=(36, 36))
        self.container = None

        self.apply_icon()
        self.build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll)

    # ------------------------------------------------------------- interface
    def apply_icon(self):
        """Icône de la fenêtre (logo.ico, sinon généré à partir du logo)."""
        path = find_data_file("logo.ico")
        if not path:
            try:
                import tempfile
                path = os.path.join(tempfile.gettempdir(), "fixitup_alert_logo.ico")
                make_logo(256).save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
            except Exception:
                return

        def _set():
            try:
                self.iconbitmap(path)
            except Exception:
                pass
        self.after(300, _set)   # customtkinter remet son icône au démarrage : on la remplace après

    def running(self) -> bool:
        return bool(self.watcher and self.watcher.is_alive())

    def build_ui(self):
        """(Re)construit toute l'interface dans la langue courante."""
        if self.container is not None:
            self.container.destroy()
        self.title(t("window"))
        c = ctk.CTkScrollableFrame(self, fg_color="transparent")
        c.pack(fill="both", expand=True)
        self.container = c

        # -- titre + drapeaux
        top = ctk.CTkFrame(c, fg_color="transparent")
        top.pack(fill="x", pady=(2, 6))
        ctk.CTkLabel(top, image=self.logo, text="").pack(side="left", padx=(4, 0))
        ctk.CTkLabel(top, text=t("title"),
                     font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=6)
        flags = ctk.CTkFrame(top, fg_color="transparent")
        flags.pack(side="right")
        for code in ("fr", "en"):
            ctk.CTkButton(
                flags, text="", image=self.flags[code], width=40, height=28,
                fg_color="#1f6aa5" if LANG == code else "transparent",
                hover_color="#3a3a3a",
                command=lambda cc=code: self.set_lang(cc),
            ).pack(side="left", padx=2)

        # -- curseur de pourcentage
        ctk.CTkLabel(c, text=t("alert_if")).pack()
        self.pct_label = ctk.CTkLabel(c, text="", font=ctk.CTkFont(size=26, weight="bold"))
        self.pct_label.pack()
        self.slider = ctk.CTkSlider(c, from_=0, to=1, number_of_steps=400,
                                    command=self.on_slider, width=340)
        self.slider.set(float(pct_to_slider(self.threshold)))
        self.slider.pack(pady=6)
        self.on_slider(self.slider.get())

        # -- choix de la méthode (une seule active)
        self.var_pct = ctk.BooleanVar(value=self.mode == "percent")
        self.var_cars = ctk.BooleanVar(value=self.mode == "cars")
        ctk.CTkCheckBox(c, text=t("m_pct"), variable=self.var_pct,
                        command=lambda: self.set_mode("percent")).pack(anchor="w", padx=20, pady=2)
        ctk.CTkCheckBox(c, text=t("m_cars"), variable=self.var_cars,
                        command=lambda: self.set_mode("cars")).pack(anchor="w", padx=20, pady=2)

        # -- recherche + liste des voitures (triée par pourcentage)
        self.search_title = ctk.CTkLabel(c, text=t("cars_search"))
        self.search_title.pack(anchor="w", padx=20, pady=(8, 0))
        srow = ctk.CTkFrame(c, fg_color="transparent")
        srow.pack(fill="x", padx=16, pady=2)
        self.search_entry = ctk.CTkEntry(srow, placeholder_text=t("search_ph"))
        self.search_entry.pack(side="left", fill="x", expand=True)
        if self.search_text:
            self.search_entry.insert(0, self.search_text)
        self.search_entry.bind("<KeyRelease>", lambda e: self.on_search())
        self.sort_btn = ctk.CTkButton(srow, text="", width=170, fg_color="gray30",
                                      command=self.toggle_sort)
        self.sort_btn.pack(side="left", padx=(6, 0))

        lrow = ctk.CTkFrame(c, fg_color="transparent")
        lrow.pack(fill="x", padx=16, pady=2)
        self.choice_list = tk.Listbox(
            lrow, height=7, selectmode="extended", activestyle="none",
            exportselection=False, bg="#2b2b2b", fg="#dce4ee",
            disabledforeground="#777777", selectbackground="#1f6aa5",
            selectforeground="white", highlightthickness=0, borderwidth=0,
            font=("Segoe UI", 10))
        sb = ctk.CTkScrollbar(lrow, command=self.choice_list.yview)
        self.choice_list.configure(yscrollcommand=sb.set)
        self.choice_list.pack(side="left", fill="x", expand=True)
        sb.pack(side="left", fill="y")
        self.choice_list.bind("<MouseWheel>", self.on_list_wheel)
        self.choice_list.bind("<Double-Button-1>", lambda e: self.add_selected())
        self.choice_list.bind("<Return>", lambda e: self.add_selected())
        self.add_btn = ctk.CTkButton(c, text=t("add"), command=self.add_selected)
        self.add_btn.pack(pady=4)

        self.cars_title = ctk.CTkLabel(c, text=t("cars_box"))
        self.cars_title.pack(anchor="w", padx=20, pady=(6, 0))
        self.cars_frame = ctk.CTkFrame(c, fg_color=("gray85", "gray17"))
        self.cars_frame.pack(fill="x", padx=16, pady=(2, 6))
        self.refresh_car_list()
        self.refresh_choices()

        # -- zone, lancer, test alarme
        ctk.CTkButton(c, text=t("select_zone"), command=self.pick_zone).pack(pady=(10, 2))
        self.zone_label = ctk.CTkLabel(c, text="", text_color="gray")
        self.zone_label.pack()
        self.refresh_zone_label()

        self.start_btn = ctk.CTkButton(
            c, height=44, font=ctk.CTkFont(size=16, weight="bold"), command=self.toggle)
        self.start_btn.pack(pady=10)
        self.refresh_start_btn()

        ctk.CTkButton(c, text=t("test"), fg_color="gray30", width=140,
                      command=self.test_alarm).pack()
        self.sound_label = ctk.CTkLabel(c, text=sound_status_text(),
                                        text_color="gray", wraplength=380)
        self.sound_label.pack(pady=(4, 0))

        # -- anti-AFK
        self.afk_var = ctk.BooleanVar(value=self.afk_worker is not None)
        ctk.CTkSwitch(c, text=t("afk"), variable=self.afk_var,
                      command=self.toggle_afk).pack(pady=(10, 0))
        self.afk_label = ctk.CTkLabel(c, text=self.afk_text(), text_color="gray", wraplength=380)
        self.afk_label.pack()

        # -- état + journal
        self.status = ctk.CTkLabel(c, text="", wraplength=380)
        self.status.pack(pady=(8, 2))
        self.render_status()

        self.log_title = ctk.CTkLabel(c, text="", text_color="gray")
        self.log_title.pack()
        self.log = ctk.CTkTextbox(c, width=380, height=130)
        self.log.pack(pady=4)
        self.raw_btn = ctk.CTkButton(c, text="", width=190, height=24,
                                     fg_color="gray30", command=self.toggle_raw)
        self.raw_btn.pack(pady=(0, 6))
        self.refresh_raw_texts()
        self.render_log()

        self.apply_mode_state()

    def set_lang(self, code):
        global LANG
        if code == LANG:
            return
        LANG = code
        self.save()
        self.build_ui()

    # -- pourcentage / méthode
    def on_slider(self, v):
        self.threshold = slider_to_pct(float(v))
        self.pct_label.configure(text=f"{fmt_pct(self.threshold)} %")

    def set_mode(self, mode):
        self.mode = mode
        self.var_pct.set(mode == "percent")
        self.var_cars.set(mode == "cars")
        self.apply_mode_state()
        self.save()

    def apply_mode_state(self):
        cars_on = self.mode == "cars"
        off_color = ("gray50", "gray50")
        on_color = ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        self.slider.configure(state="disabled" if cars_on else "normal")
        self.pct_label.configure(text_color=off_color if cars_on else on_color)
        for w in (self.search_entry, self.add_btn, self.sort_btn):
            w.configure(state="normal" if cars_on else "disabled")
        self.choice_list.configure(state="normal" if cars_on else "disabled")
        for w in (self.search_title, self.cars_title):
            w.configure(text_color=on_color if cars_on else off_color)
        for w in self.cars_frame.winfo_children():
            for sub in w.winfo_children():
                try:
                    if isinstance(sub, ctk.CTkButton):
                        sub.configure(state="normal" if cars_on else "disabled")
                    else:
                        sub.configure(text_color=on_color if cars_on else off_color)
                except Exception:
                    pass

    # -- recherche / choix des voitures
    def on_search(self):
        self.search_text = self.search_entry.get()
        self.refresh_choices()

    def toggle_sort(self):
        self.sort_asc = not self.sort_asc
        self.refresh_choices()

    def on_list_wheel(self, event):
        self.choice_list.yview_scroll(-2 if event.delta > 0 else 2, "units")
        return "break"          # la molette ne fait pas défiler la fenêtre en plus

    def refresh_choices(self):
        self.choice_names = car_choices(self.search_text, self.selected, self.sort_asc)
        lb = self.choice_list
        lb.configure(state="normal")
        lb.delete(0, "end")
        for n in self.choice_names:
            lb.insert("end", car_label(n))
        if not self.choice_names:
            lb.insert("end", t("no_results"))
        lb.configure(state="normal" if self.mode == "cars" else "disabled")
        self.sort_btn.configure(text=t("sort_rare") if self.sort_asc else t("sort_common"))

    def add_selected(self):
        if self.mode != "cars":
            return
        names = [self.choice_names[i] for i in self.choice_list.curselection()
                 if i < len(self.choice_names)]
        if not names:
            txt = self.search_text.strip()
            if len(self.choice_names) == 1:
                names = [self.choice_names[0]]
            elif not self.choice_names and len(norm_key(txt)) >= 3:
                names = [txt]          # nom absent de la liste, saisi à la main
        if not names:
            return
        for n in names:
            if not any(norm_key(n) == norm_key(x) for x in self.selected):
                self.selected.append(n)
        self.save()
        self.refresh_car_list()
        self.refresh_choices()
        self.apply_mode_state()

    def remove_car(self, name):
        self.selected = [x for x in self.selected if x != name]
        self.save()
        self.refresh_car_list()
        self.refresh_choices()
        self.apply_mode_state()

    def refresh_car_list(self):
        for w in self.cars_frame.winfo_children():
            w.destroy()
        if not self.selected:
            ctk.CTkLabel(self.cars_frame, text=t("no_cars"),
                         text_color="gray").pack(pady=6)
            return
        for name in self.selected:
            row = ctk.CTkFrame(self.cars_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=1)
            ctk.CTkLabel(row, text=car_label(name), anchor="w").pack(side="left")
            ctk.CTkButton(row, text="✕", width=28, height=24, fg_color="#7a2d2d",
                          hover_color="#a33", command=lambda n=name: self.remove_car(n)
                          ).pack(side="right")

    def get_rule(self):
        return (self.mode, self.threshold, [norm_key(n) for n in self.selected])

    # -- zone
    def refresh_zone_label(self):
        if self.region:
            r = self.region
            self.zone_label.configure(text=t("zone_size", w=r["width"], h=r["height"]))
        else:
            self.zone_label.configure(text=t("zone_none"))

    def pick_zone(self):
        self.withdraw()
        self.after(250, lambda: ZoneSelector(self, self.zone_done))

    def zone_done(self, region):
        self.region = region
        self.deiconify()
        self.refresh_zone_label()
        self.save()

    def save(self):
        save_config({"region": self.region, "threshold": self.threshold,
                     "lang": LANG, "mode": self.mode, "cars": self.selected})

    # -- alarme
    def test_alarm(self):
        self.show_alert(t("test_car"), 0.5)
        self.sound_label.configure(text=sound_status_text())
        # le résultat de l'ouverture du fichier son arrive un instant plus tard
        self.after(800, lambda: self.sound_label.configure(text=sound_status_text()))

    # -- anti-AFK
    def afk_text(self) -> str:
        if self.afk_worker is None:
            return t("afk_off")
        if self.afk_last is None:
            return t("afk_wait", m=AFK_INTERVAL_MIN)
        status, hhmm = self.afk_last
        key = {"sent": "afk_sent", "active": "afk_active", "none": "afk_none"}[status]
        return t(key, t=hhmm)

    def toggle_afk(self):
        if self.afk_var.get():
            self.afk_last = None
            self.afk_worker = AfkWorker(self.q)
            self.afk_worker.start()
        elif self.afk_worker:
            self.afk_worker.stop()
            self.afk_worker = None
        self.afk_label.configure(text=self.afk_text())

    # -- état / journal
    def refresh_start_btn(self):
        if self.running():
            self.start_btn.configure(text=t("stop"), fg_color="#c0392b", hover_color="#962d22")
        else:
            self.start_btn.configure(text=t("start"), fg_color="#2e8b57", hover_color="#256f46")

    def render_status(self):
        st = self.status_state
        if st[0] == "running" and self.running():
            self.status.configure(text=t("st_running", n=self.cars_seen), text_color="#2ecc71")
        elif st[0] == "zone":
            self.status.configure(text=t("st_zone"), text_color="orange")
        elif st[0] == "cars":
            self.status.configure(text=t("st_cars"), text_color="orange")
        elif st[0] == "error":
            key = {"tess": "err_tess", "read": "err_read", "gen": "err_gen"}.get(st[1], "err_gen")
            self.status.configure(text=t(key, e=st[2]), text_color="orange")
        else:
            self.status.configure(text=t("st_stopped"), text_color="gray")

    @staticmethod
    def format_event(ev) -> str:
        ts, kind, a, b = ev
        if kind == "base":
            msg = t("ev_base", n=a)
        else:
            key = {"alert": "ev_alert", "ign_pct": "ev_ign_pct", "ign_list": "ev_ign_list"}[kind]
            msg = t(key, name=a, pct=fmt_pct(b))
        return f"{ts}  {msg}"

    def refresh_raw_texts(self):
        self.log_title.configure(text=t("log_raw") if self.raw_mode else t("log_hist"))
        self.raw_btn.configure(text=t("btn_hist") if self.raw_mode else t("btn_raw"))

    def render_log(self):
        """Affiche l'historique (défilement en bas) ou le texte brut (le
        défilement choisi par l'utilisateur est conservé)."""
        try:
            top = self.log.yview()[0]
        except Exception:
            top = 0.0
        if self.raw_mode:
            content = self.last_text or t("empty_raw")
        else:
            content = "\n".join(self.format_event(e) for e in self.events) or t("empty_hist")
        self.log.delete("1.0", "end")
        self.log.insert("1.0", content)
        try:
            self.log.yview("moveto", top if self.raw_mode else 1.0)
        except Exception:
            pass

    def toggle_raw(self):
        self.raw_mode = not self.raw_mode
        self.refresh_raw_texts()
        self.render_log()

    # -- start / stop
    def toggle(self):
        if self.running():
            self.watcher.stop()
            self.watcher = None
            self.status_state = ("stopped",)
            self.refresh_start_btn()
            self.render_status()
            return
        if not self.region:
            self.status_state = ("zone",)
            self.render_status()
            return
        if self.mode == "cars" and not self.selected:
            self.status_state = ("cars",)
            self.render_status()
            return
        self.save()
        self.cars_seen = 0
        self.watcher = Watcher(self.region, self.get_rule, self.q)
        self.watcher.start()
        self.status_state = ("running",)
        self.refresh_start_btn()
        self.render_status()

    # -- messages venant des threads
    def poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "text":
                    if data != self.last_text:
                        self.last_text = data
                        if self.raw_mode:
                            self.render_log()
                elif kind == "event":
                    self.events = (self.events + [data])[-200:]
                    if not self.raw_mode:
                        self.render_log()
                elif kind == "count":
                    if data != self.cars_seen and self.running():
                        self.cars_seen = data
                        self.render_status()
                elif kind == "alert":
                    self.show_alert(*data)
                elif kind == "afk":
                    self.afk_last = data
                    if self.afk_worker:
                        self.afk_label.configure(text=self.afk_text())
                elif kind == "error":
                    if self.watcher:
                        self.watcher.stop()
                        self.watcher = None
                    self.status_state = ("error", data[0], data[1])
                    self.refresh_start_btn()
                    self.render_status()
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def show_alert(self, name, pct):
        if self.popup:
            self.popup.close()
        self.popup = AlertPopup(self, name, pct)

    def on_close(self):
        self.save()
        if self.watcher:
            self.watcher.stop()
        if self.afk_worker:
            self.afk_worker.stop()
        if self.popup:
            self.popup.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
