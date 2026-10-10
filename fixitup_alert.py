"""
Fix It Up - Alerte voiture rare  (v1.3)

Lit le chat Roblox (zone choisie) par OCR et détecte les messages de la forme :
    [System] A rare car has appeared! <Nom de la voiture> — Chance: 4%
Si le pourcentage est <= au seuil, popup + alarme.
Les anciens messages qui réapparaissent quand le chat se réaffiche sont ignorés.
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


def resource_path(rel: str) -> str:
    """Chemin d'un fichier embarqué (marche en .py et en .exe PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# Dossier où se trouve l'appli (là où tu déposes ton fichier alarme)
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
            for t in types:
                err, msg = _mci(f'open "{self.path}" type {t} alias {alias}')
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
            last_alarm_error = f"Impossible de lire {os.path.basename(self.path)} ({err_msg})"
        # Bips (aucun fichier, ou fichier illisible)
        while not self.stop_event.is_set():
            for freq, dur in ALARM_BEEPS:
                if self.stop_event.is_set():
                    break
                winsound.Beep(freq, dur)


def sound_status_text() -> str:
    p = find_alarm_file()
    if last_alarm_error:
        return f"Son : {last_alarm_error} → bips utilisés"
    if p:
        return f"Son : {os.path.basename(p)}"
    return f"Son : bips (aucun fichier « alarme » trouvé dans {APP_DIR})"


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
            text="Dessine un rectangle sur le chat  (Échap = annuler)",
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

    def __init__(self, region, get_threshold, out_queue):
        super().__init__(daemon=True)
        self.region = region
        self.get_threshold = get_threshold
        self.q = out_queue
        self.stop_event = threading.Event()
        self.known = {}            # clé voiture -> {"count", "absent", "pct"} (déjà lues)
        self.pending = {}          # nouvelles voitures en cours de confirmation
        self.notes = []            # messages d'info pour l'historique
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
                self.notes.append(f"{old} voiture(s) déjà dans le chat : ignorée(s)")

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
                        self.q.put(("error", "Tesseract introuvable. Installe-le (voir étapes)."))
                        return
                    except Exception as ex:
                        self.q.put(("error", f"Erreur lecture : {ex}"))
                        time.sleep(1)
                        continue

                    self.q.put(("text", text.strip()))
                    cars = extract_cars(text)
                    self.q.put(("count", len(cars)))
                    threshold = self.get_threshold()
                    found = self.process(text, cars, time.time())
                    for note in self.notes:
                        self.q.put(("event", f"{time.strftime('%H:%M:%S')}  {note}"))
                    self.notes.clear()
                    for name, pct in found:
                        ts = time.strftime("%H:%M:%S")
                        if pct <= threshold:
                            self.q.put(("event", f"{ts}  {name} — {fmt_pct(pct)} %  → ALERTE"))
                            self.q.put(("alert", (name, pct)))
                        else:
                            self.q.put(("event", f"{ts}  {name} — {fmt_pct(pct)} %  (au-dessus du seuil)"))
                    time.sleep(SCAN_DELAY)
        except Exception as ex:
            self.q.put(("error", f"Erreur : {ex}"))


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

        tk.Label(self.win, text="🚗 VOITURE RARE !", bg="#c0392b", fg="white",
                 font=("Segoe UI", 22, "bold")).pack(pady=(14, 2))
        tk.Label(self.win, text=name, bg="#c0392b", fg="white", wraplength=520,
                 font=("Segoe UI", 18)).pack()
        tk.Label(self.win, text=f"{fmt_pct(pct)} %", bg="#c0392b", fg="#ffe066",
                 font=("Segoe UI", 26, "bold")).pack(pady=2)
        tk.Button(self.win, text="FERMER (Échap)", command=self.close,
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
        ctk.set_appearance_mode("dark")
        self.title("Fix It Up - Alerte")
        self.geometry("400x640")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        cfg = load_config()
        self.region = cfg.get("region")
        self.threshold = cfg.get("threshold", 1.0)
        self.q = queue.Queue()
        self.watcher = None
        self.popup = None
        self.last_text = ""
        self.events = []           # historique des voitures détectées
        self.raw_mode = False      # False = historique, True = texte brut lu (debug)
        self.cars_seen = 0

        ctk.CTkLabel(self, text="Alerte voiture rare",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(16, 4))

        ctk.CTkLabel(self, text="Alerter si rareté ≤").pack()
        self.pct_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=26, weight="bold"))
        self.pct_label.pack()
        self.slider = ctk.CTkSlider(self, from_=0, to=1, number_of_steps=400,
                                    command=self.on_slider, width=320)
        self.slider.set(float(pct_to_slider(self.threshold)))
        self.slider.pack(pady=6)
        self.on_slider(self.slider.get())

        self.zone_btn = ctk.CTkButton(self, text="Sélectionner la zone", command=self.pick_zone)
        self.zone_btn.pack(pady=(14, 2))
        self.zone_label = ctk.CTkLabel(self, text="", text_color="gray")
        self.zone_label.pack()
        self.refresh_zone_label()

        self.start_btn = ctk.CTkButton(self, text="Lancer", fg_color="#2e8b57",
                                       hover_color="#256f46", height=44,
                                       font=ctk.CTkFont(size=16, weight="bold"),
                                       command=self.toggle)
        self.start_btn.pack(pady=12)

        self.test_btn = ctk.CTkButton(self, text="Tester l'alarme", fg_color="gray30",
                                      width=140, command=self.test_alarm)
        self.test_btn.pack()
        self.sound_label = ctk.CTkLabel(self, text=sound_status_text(),
                                        text_color="gray", wraplength=360)
        self.sound_label.pack(pady=(4, 0))

        self.status = ctk.CTkLabel(self, text="Arrêté", text_color="gray")
        self.status.pack(pady=(8, 2))

        self.log_title = ctk.CTkLabel(self, text="Historique des détections :",
                                      text_color="gray")
        self.log_title.pack()
        self.log = ctk.CTkTextbox(self, width=360, height=130)
        self.log.pack(pady=4)
        self.raw_btn = ctk.CTkButton(self, text="Voir le texte lu (debug)", width=180,
                                     height=24, fg_color="gray30", command=self.toggle_raw)
        self.raw_btn.pack(pady=(0, 6))
        self.render_log()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll)

    # -- interface
    def on_slider(self, v):
        self.threshold = slider_to_pct(float(v))
        self.pct_label.configure(text=f"{fmt_pct(self.threshold)} %")

    def refresh_zone_label(self):
        if self.region:
            r = self.region
            self.zone_label.configure(text=f"Zone : {r['width']}x{r['height']} px")
        else:
            self.zone_label.configure(text="Aucune zone sélectionnée")

    def pick_zone(self):
        self.withdraw()
        self.after(250, lambda: ZoneSelector(self, self.zone_done))

    def zone_done(self, region):
        self.region = region
        self.deiconify()
        self.refresh_zone_label()
        self.save()

    def save(self):
        save_config({"region": self.region, "threshold": self.threshold})

    def render_log(self):
        """Affiche l'historique (défilement en bas) ou le texte brut (le
        défilement choisi par l'utilisateur est conservé)."""
        try:
            top = self.log.yview()[0]
        except Exception:
            top = 0.0
        if self.raw_mode:
            content = self.last_text or "(aucun texte détecté)"
        else:
            content = "\n".join(self.events) or "(rien détecté pour l'instant)"
        self.log.delete("1.0", "end")
        self.log.insert("1.0", content)
        try:
            self.log.yview("moveto", top if self.raw_mode else 1.0)
        except Exception:
            pass

    def toggle_raw(self):
        self.raw_mode = not self.raw_mode
        self.log_title.configure(
            text="Texte lu sur l'écran (debug) :" if self.raw_mode
            else "Historique des détections :")
        self.raw_btn.configure(
            text="Voir l'historique" if self.raw_mode else "Voir le texte lu (debug)")
        self.render_log()

    def test_alarm(self):
        self.show_alert("Test Voiture", 0.5)
        self.sound_label.configure(text=sound_status_text())
        # le résultat de l'ouverture du fichier son arrive un instant plus tard
        self.after(800, lambda: self.sound_label.configure(text=sound_status_text()))

    # -- start / stop
    def set_running_status(self):
        self.status.configure(
            text=f"Surveillance en cours… (messages voiture lus : {self.cars_seen})",
            text_color="#2ecc71")

    def toggle(self):
        if self.watcher and self.watcher.is_alive():
            self.watcher.stop()
            self.watcher = None
            self.start_btn.configure(text="Lancer", fg_color="#2e8b57", hover_color="#256f46")
            self.status.configure(text="Arrêté", text_color="gray")
            return
        if not self.region:
            self.status.configure(text="Sélectionne d'abord une zone", text_color="orange")
            return
        self.save()
        self.cars_seen = 0
        self.watcher = Watcher(self.region, lambda: self.threshold, self.q)
        self.watcher.start()
        self.start_btn.configure(text="Éteindre", fg_color="#c0392b", hover_color="#962d22")
        self.set_running_status()

    # -- messages venant du thread
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
                    if data != self.cars_seen and self.watcher:
                        self.cars_seen = data
                        self.set_running_status()
                elif kind == "alert":
                    self.show_alert(*data)
                elif kind == "error":
                    self.status.configure(text=data, text_color="orange")
                    if self.watcher:
                        self.watcher.stop()
                        self.watcher = None
                    self.start_btn.configure(text="Lancer", fg_color="#2e8b57", hover_color="#256f46")
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
        if self.popup:
            self.popup.close()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
