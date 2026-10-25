"""
QuickAsk - surligne un texte, appuie sur le raccourci, la reponse de Claude Code
arrive dans le presse-papier. Tourne en fond avec une icone dans la zone de notification.

Icone :  bleu = pret | orange = en cours | vert = reponse copiee | rouge = erreur (voir quickask.log)

v2 : raccourci gere par l'API Windows (RegisterHotKey) au lieu de la lib "keyboard".
"""
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from ctypes import wintypes

import pyperclip
import pystray
from PIL import Image, ImageDraw

APP_DIR = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")
LOG_PATH = os.path.join(APP_DIR, "quickask.log")

DEFAULT_CONFIG = {
    "hotkey": "ctrl+shift+q",
    # Garder sans caracteres speciaux (& | ^ % ! " ') car passe en argument a claude
    "instruction": "Answer in English in one sentence of 15 words max, no explanation, no introduction, no Markdown",
    "timeout": 120,
    "claude_path": "",
}

IDLE, BUSY, DONE, ERROR = (70, 130, 220), (240, 150, 30), (40, 170, 80), (210, 50, 50)
_busy = threading.Lock()

user32 = ctypes.WinDLL("user32", use_last_error=True) if os.name == "nt" else None
kernel32 = ctypes.WinDLL("kernel32") if os.name == "nt" else None

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
KEYEVENTF_KEYUP = 0x2
HOTKEY_ID = 1


def log(msg):
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception as e:
            log(f"config.json illisible, valeurs par defaut utilisees : {e}")
    else:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
    return cfg


def parse_hotkey(text):
    """'ctrl+shift+q' -> (modificateurs, code de touche). Touches : A-Z, 0-9, F1-F24."""
    mods, vk = 0, None
    for part in text.lower().replace(" ", "").split("+"):
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part == "alt":
            mods |= MOD_ALT
        elif part in ("win", "windows"):
            mods |= MOD_WIN
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        else:
            raise ValueError(f"Touche inconnue dans le raccourci : '{part}'")
    if vk is None:
        raise ValueError(f"Raccourci sans touche principale : '{text}'")
    return mods, vk


def make_icon(color):
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 58, 58), fill=color)
    d.text((25, 20), "?", fill=(255, 255, 255))
    return img


def set_icon(icon, color, reset_after=None):
    icon.icon = make_icon(color)
    if reset_after:
        threading.Timer(reset_after, lambda: set_icon(icon, IDLE)).start()


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def wait_modifiers_released(timeout=2.0):
    # Sinon le Ctrl+C simule devient Ctrl+Maj+C (ouvre l'inspecteur dans Chrome)
    end = time.time() + timeout
    while time.time() < end and any(key_down(k) for k in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN)):
        time.sleep(0.02)


def send_ctrl_c():
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(ord("C"), 0, 0, 0)
    user32.keybd_event(ord("C"), 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def copy_selection():
    """Copie le texte surligne (Ctrl+C simule) et le renvoie."""
    wait_modifiers_released()
    try:
        previous = pyperclip.paste()
    except Exception:
        previous = ""
    sentinel = f"__quickask_{time.time()}__"
    pyperclip.copy(sentinel)
    send_ctrl_c()
    end = time.time() + 1.5
    while time.time() < end:
        time.sleep(0.05)
        current = pyperclip.paste()
        if current != sentinel:
            return current
    pyperclip.copy(previous)  # rien de surligne : on remet l'ancien contenu
    return ""


def find_claude(cfg):
    p = cfg.get("claude_path")
    if p and os.path.exists(p):
        return p
    for name in ("claude", "claude.cmd", "claude.exe"):
        found = shutil.which(name)
        if found:
            return found
    candidate = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")
    return candidate if os.path.exists(candidate) else None


def ask_claude(cfg, text):
    exe = find_claude(cfg)
    if not exe:
        raise RuntimeError("Claude Code introuvable. Mets le chemin complet dans claude_path (config.json).")
    log(f"Appel de Claude Code : {exe}")
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW : pas de fenetre console
    r = subprocess.run(
        [exe, "-p", cfg["instruction"]],
        input=text.encode("utf-8"),
        capture_output=True,
        timeout=cfg["timeout"],
        cwd=tempfile.gettempdir(),
        creationflags=flags,
    )
    out = r.stdout.decode("utf-8", errors="replace").strip()
    if r.returncode != 0 or not out:
        err = r.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"claude a renvoye le code {r.returncode} : {err or 'reponse vide'}")
    return out


def handle(cfg, icon):
    if not _busy.acquire(blocking=False):
        return  # une demande est deja en cours
    try:
        text = copy_selection().strip()
        if not text:
            log("Aucun texte surligne recupere")
            set_icon(icon, ERROR, reset_after=2)
            return
        set_icon(icon, BUSY)
        answer = ask_claude(cfg, text)
        pyperclip.copy(answer)
        log("Reponse copiee")
        set_icon(icon, DONE, reset_after=3)
    except Exception:
        log(traceback.format_exc())
        set_icon(icon, ERROR, reset_after=4)
    finally:
        _busy.release()


def hotkey_loop(cfg, icon, state):
    """Enregistre le raccourci aupres de Windows et attend les WM_HOTKEY."""
    state["thread_id"] = kernel32.GetCurrentThreadId()
    try:
        mods, vk = parse_hotkey(cfg["hotkey"])
    except ValueError as e:
        log(str(e))
        set_icon(icon, ERROR)
        return
    if not user32.RegisterHotKey(None, HOTKEY_ID, mods | MOD_NOREPEAT, vk):
        err = ctypes.get_last_error()
        hint = " (deja utilise par une autre appli, change-le dans config.json)" if err == 1409 else ""
        log(f"Impossible d'enregistrer le raccourci {cfg['hotkey']}, erreur Windows {err}{hint}")
        set_icon(icon, ERROR)
        return
    log(f"Raccourci {cfg['hotkey']} enregistre")
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                log("Raccourci detecte")
                threading.Thread(target=handle, args=(cfg, icon), daemon=True).start()
    finally:
        user32.UnregisterHotKey(None, HOTKEY_ID)


def main():
    if os.name != "nt":
        print("QuickAsk fonctionne uniquement sous Windows.")
        return
    cfg = load_config()
    state = {}

    def open_folder(icon, item):
        os.startfile(APP_DIR)

    def quit_app(icon, item):
        tid = state.get("thread_id")
        if tid:
            user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
        icon.stop()

    icon = pystray.Icon(
        "QuickAsk",
        make_icon(IDLE),
        "QuickAsk",
        menu=pystray.Menu(
            pystray.MenuItem(f"Raccourci : {cfg['hotkey']}", lambda i, it: None, enabled=False),
            pystray.MenuItem("Ouvrir le dossier", open_folder),
            pystray.MenuItem("Quitter", quit_app),
        ),
    )
    log("Demarre (v2)")
    threading.Thread(target=hotkey_loop, args=(cfg, icon, state), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
