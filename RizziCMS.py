#!/usr/bin/env python3
"""
Rizzi CMS — Launcher GUI per Mac
Doppio click su questo file per avviare tutto.
"""

import tkinter as tk
from tkinter import font as tkfont
import subprocess
import threading
import webbrowser
import sys
import os
import time
import socket

# ── Percorso base: la cartella dove si trova questo file ──────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 5151
SITE_URL = f"http://localhost:{PORT}/"
CMS_URL  = f"http://localhost:{PORT}/cms"

# ── Colori ────────────────────────────────────────────────────────────────────
BG        = "#0a0a0a"
BG_CARD   = "#141414"
ACCENT    = "#ffffff"
GRAY      = "#555555"
GRAY_LIGHT= "#888888"
GREEN     = "#22c55e"
RED       = "#ef4444"
YELLOW    = "#eab308"

server_process = None
status = "stopped"  # stopped | starting | running

# ── Verifica se la porta è già in uso ─────────────────────────────────────────
def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(('127.0.0.1', port)) == 0

# ── Installa dipendenze se mancanti ───────────────────────────────────────────
def ensure_deps():
    try:
        import flask
        from PIL import Image
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "flask", "pillow", "-q"],
            cwd=BASE_DIR
        )

# ── Avvia il server Flask ─────────────────────────────────────────────────────
def start_server():
    global server_process, status
    status = "starting"
    update_ui()

    ensure_deps()

    server_process = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BASE_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    # Aspetta che il server risponda (max 8 secondi)
    for _ in range(16):
        time.sleep(0.5)
        if is_port_open(PORT):
            status = "running"
            update_ui()
            return

    status = "stopped"
    update_ui()

def stop_server():
    global server_process, status
    if server_process:
        server_process.terminate()
        server_process = None
    status = "stopped"
    update_ui()

def toggle_server():
    if status == "running":
        threading.Thread(target=stop_server, daemon=True).start()
    else:
        threading.Thread(target=start_server, daemon=True).start()

# ── Aggiorna l'interfaccia ────────────────────────────────────────────────────
def update_ui():
    root.after(0, _update_ui_main_thread)

def _update_ui_main_thread():
    if status == "running":
        btn_toggle.config(text="  Ferma  ", bg=RED, activebackground="#dc2626")
        lbl_status.config(text="● In esecuzione", fg=GREEN)
        btn_site.config(state="normal", fg=ACCENT, cursor="hand2")
        btn_cms.config(state="normal", fg=ACCENT, cursor="hand2")
        lbl_site_url.config(fg=GRAY_LIGHT)
        lbl_cms_url.config(fg=GRAY_LIGHT)
    elif status == "starting":
        btn_toggle.config(text=" Avvio... ", bg=YELLOW, activebackground=YELLOW)
        lbl_status.config(text="● Avvio in corso...", fg=YELLOW)
        btn_site.config(state="disabled", fg=GRAY, cursor="arrow")
        btn_cms.config(state="disabled", fg=GRAY, cursor="arrow")
        lbl_site_url.config(fg=GRAY)
        lbl_cms_url.config(fg=GRAY)
    else:
        btn_toggle.config(text="  Avvia  ", bg=ACCENT, activebackground="#dddddd")
        lbl_status.config(text="● Fermo", fg=GRAY_LIGHT)
        btn_site.config(state="disabled", fg=GRAY, cursor="arrow")
        btn_cms.config(state="disabled", fg=GRAY, cursor="arrow")
        lbl_site_url.config(fg=GRAY)
        lbl_cms_url.config(fg=GRAY)

def open_site():
    if status == "running":
        webbrowser.open(SITE_URL)

def open_cms():
    if status == "running":
        webbrowser.open(CMS_URL)

def on_close():
    stop_server()
    root.destroy()

# ── Interfaccia ───────────────────────────────────────────────────────────────
root = tk.Tk()
root.title("Rizzi CMS")
root.geometry("360x420")
root.resizable(False, False)
root.configure(bg=BG)
root.protocol("WM_DELETE_WINDOW", on_close)

# Centra la finestra
root.update_idletasks()
x = (root.winfo_screenwidth()  // 2) - 180
y = (root.winfo_screenheight() // 2) - 210
root.geometry(f"360x420+{x}+{y}")

# Font
try:
    f_title  = tkfont.Font(family="SF Pro Display", size=18, weight="bold")
    f_sub    = tkfont.Font(family="SF Pro Text",    size=11)
    f_btn    = tkfont.Font(family="SF Pro Text",    size=13, weight="bold")
    f_label  = tkfont.Font(family="SF Pro Text",    size=10)
    f_url    = tkfont.Font(family="SF Mono",        size=10)
    f_status = tkfont.Font(family="SF Pro Text",    size=11)
except:
    f_title  = tkfont.Font(family="Helvetica Neue", size=18, weight="bold")
    f_sub    = tkfont.Font(family="Helvetica Neue", size=11)
    f_btn    = tkfont.Font(family="Helvetica Neue", size=13, weight="bold")
    f_label  = tkfont.Font(family="Helvetica Neue", size=10)
    f_url    = tkfont.Font(family="Courier New",    size=10)
    f_status = tkfont.Font(family="Helvetica Neue", size=11)

# ── Titolo ────────────────────────────────────────────────────────────────────
tk.Frame(root, bg=BG, height=28).pack()
tk.Label(root, text="Rizzi CMS", font=f_title, bg=BG, fg=ACCENT).pack()
tk.Label(root, text="Gestione Portfolio", font=f_sub, bg=BG, fg=GRAY_LIGHT).pack(pady=(2,0))

# ── Separatore ────────────────────────────────────────────────────────────────
tk.Frame(root, bg=GRAY, height=1, width=300).pack(pady=20)

# ── Stato ─────────────────────────────────────────────────────────────────────
lbl_status = tk.Label(root, text="● Fermo", font=f_status, bg=BG, fg=GRAY_LIGHT)
lbl_status.pack()

# ── Bottone Avvia/Ferma ───────────────────────────────────────────────────────
tk.Frame(root, bg=BG, height=12).pack()
btn_toggle = tk.Button(
    root, text="  Avvia  ", font=f_btn,
    bg=ACCENT, fg=BG, activeforeground=BG,
    activebackground="#dddddd",
    relief="flat", bd=0, padx=24, pady=10,
    cursor="hand2", command=toggle_server
)
btn_toggle.pack()

# ── Separatore ────────────────────────────────────────────────────────────────
tk.Frame(root, bg=GRAY, height=1, width=300).pack(pady=20)

# ── Card Sito ─────────────────────────────────────────────────────────────────
frame_site = tk.Frame(root, bg=BG_CARD, padx=20, pady=14, width=300)
frame_site.pack(padx=30, fill="x")
frame_site.pack_propagate(False)

row1 = tk.Frame(frame_site, bg=BG_CARD)
row1.pack(fill="x")
tk.Label(row1, text="Sito", font=f_label, bg=BG_CARD, fg=GRAY_LIGHT).pack(side="left")
btn_site = tk.Button(
    row1, text="Apri →", font=f_label,
    bg=BG_CARD, fg=GRAY, relief="flat", bd=0,
    activebackground=BG_CARD, activeforeground=ACCENT,
    state="disabled", command=open_site
)
btn_site.pack(side="right")
lbl_site_url = tk.Label(frame_site, text=SITE_URL, font=f_url, bg=BG_CARD, fg=GRAY)
lbl_site_url.pack(anchor="w", pady=(4,0))

tk.Frame(root, bg=BG, height=8).pack()

# ── Card CMS ──────────────────────────────────────────────────────────────────
frame_cms = tk.Frame(root, bg=BG_CARD, padx=20, pady=14, width=300)
frame_cms.pack(padx=30, fill="x")
frame_cms.pack_propagate(False)

row2 = tk.Frame(frame_cms, bg=BG_CARD)
row2.pack(fill="x")
tk.Label(row2, text="CMS", font=f_label, bg=BG_CARD, fg=GRAY_LIGHT).pack(side="left")
btn_cms = tk.Button(
    row2, text="Apri →", font=f_label,
    bg=BG_CARD, fg=GRAY, relief="flat", bd=0,
    activebackground=BG_CARD, activeforeground=ACCENT,
    state="disabled", command=open_cms
)
btn_cms.pack(side="right")
lbl_cms_url = tk.Label(frame_cms, text=CMS_URL, font=f_url, bg=BG_CARD, fg=GRAY)
lbl_cms_url.pack(anchor="w", pady=(4,0))

# ── Footer ────────────────────────────────────────────────────────────────────
tk.Frame(root, bg=BG, height=16).pack()
tk.Label(root, text="Chiudi questa finestra per fermare il server",
         font=f_label, bg=BG, fg=GRAY).pack()

# ── Avvio ─────────────────────────────────────────────────────────────────────
# Se il server è già in esecuzione (es. riavvio app), rileva lo stato
if is_port_open(PORT):
    status = "running"
    update_ui()

root.mainloop()
