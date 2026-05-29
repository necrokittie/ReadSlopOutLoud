#!/usr/bin/env python3
"""
Read Slop Out Loud — Standalone TTS Reader
Copied from Sloppa Engine 9000's Read Out Loud feature.
Paste text, pick a Kokoro voice, play out loud or convert files to MP3.
"""

import sys
import os
import subprocess
import threading
import time
import re
import traceback
import datetime
import warnings
import numpy as np
from pathlib import Path
from tempfile import gettempdir
from tkinter import (
    Tk, Frame, Label, Button, Entry, Scrollbar, StringVar,
    DoubleVar, BooleanVar, Scale, END, LEFT, RIGHT, W, E, W, EW, NS, NSEW,
    HORIZONTAL, DISABLED, NORMAL, Text, INSERT, Toplevel, BOTH, YES, Menu,
    Canvas, VERTICAL, messagebox, filedialog
)
from tkinter import ttk

# ─────────────────────────── COLOR THEMES ───────────────────────────

DARK = {
    "BG":       "#0d0d0d",
    "PANEL":    "#1a1a1a",
    "INPUT":    "#242424",
    "BORDER":   "#383838",
    "FG":       "#ffffff",
    "FG2":      "#aaaaaa",
    "FG3":      "#555555",
    "ACCENT":   "#5F4A8B",
    "ACCENT_H": "#7a5fb8",
    "OK_COL":    "#4CAF50",
    "ERR_COL":   "#f44336",
    "WARN_COL":  "#FFA726",
    "HIGHLIGHT_BG": "#d4380d",
    "HIGHLIGHT_FG": "#ffffff",
    "COMBO_BG":  "#333333",
    "COMBO_FG":  "#ffffff",
}

LIGHT = {
    "BG":       "#FDE8E9",
    "PANEL":    "#FFB7C5",
    "INPUT":    "#ffffff",
    "BORDER":   "#F9C6CF",
    "FG":       "#A2646F",
    "FG2":      "#8a4b55",
    "FG3":      "#c48b96",
    "ACCENT":   "#FFB7C5",
    "ACCENT_H": "#ff9aad",
    "OK_COL":    "#6b8f71",
    "ERR_COL":   "#c44b5e",
    "WARN_COL":  "#d9996b",
    "HIGHLIGHT_BG": "#FFB7C5",
    "HIGHLIGHT_FG": "#A2646F",
    "COMBO_BG":  "#ffffff",
    "COMBO_FG":  "#A2646F",
}

PURPLE_ACCENT = "#5F4A8B"

_SETTINGS_FILE = Path(__file__).with_name("theme.settings")

def _load_theme_setting():
    try:
        data = _SETTINGS_FILE.read_text(encoding="utf-8").strip()
        return data if data in ("dark", "gay") else None
    except Exception:
        return None

def _save_theme_setting(mode):
    try:
        _SETTINGS_FILE.write_text(mode, encoding="utf-8")
    except Exception:
        pass

_saved = _load_theme_setting()
if _saved == "gay":
    THEME = dict(LIGHT)
else:
    THEME = dict(DARK)

# ─────────────────────────── VOICES ───────────────────────────

VOICES = {
    "am_adam    Deep American Male [default]":  "am_adam",
    "am_michael  Warm American Male":           "am_michael",
    "am_fenrir   Gruff Intense Male":           "am_fenrir",
    "am_puck     Light Quick Male":             "am_puck",
    "am_echo     Clear Measured Male":          "am_echo",
    "am_eric     Steady Composed Male":         "am_eric",
    "am_liam     Younger American Male":        "am_liam",
    "am_onyx     Rich Authoritative Male":      "am_onyx",
    "bm_george   Composed British Male":        "bm_george",
    "bm_lewis    Intense British Male":         "bm_lewis",
    "bm_daniel   Neutral British Male":         "bm_daniel",
    "bm_fable    Storyteller British Male":     "bm_fable",
    "af_heart    Warm American Female":         "af_heart",
    "af_bella    Expressive American Female":   "af_bella",
    "af_nicole   Smooth American Female":       "af_nicole",
    "af_aoede    Dramatic American Female":     "af_aoede",
    "af_kore     Cool American Female":         "af_kore",
    "af_sarah    Natural American Female":      "af_sarah",
    "af_nova     Strong American Female":       "af_nova",
    "af_sky      Airy American Female":         "af_sky",
    "af_jessica  Engaging American Female":     "af_jessica",
    "af_river    Calm American Female":         "af_river",
    "bf_emma     Authoritative British Female": "bf_emma",
    "bf_isabella Elegant British Female":       "bf_isabella",
    "bf_alice    Warm British Female":          "bf_alice",
    "bf_lily     Gentle British Female":        "bf_lily",
}


# ─────────────────────────── KOKORO BRIDGE ───────────────────────────

_kokoro_cache = {}

def _get_pipeline(voice_id, status_cb=None):
    import os as _os
    import logging
    if not _os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS"):
        _os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=FutureWarning, module="torch.nn.utils.weight_norm")
    warnings.filterwarnings("ignore", category=UserWarning, module="torch.nn.modules.rnn")
    from kokoro import KPipeline
    lang = "b" if voice_id.startswith("b") else "a"
    if lang not in _kokoro_cache:
        voice_name = voice_id.replace("_", " ").title()
        if status_cb:
            status_cb(f"Loading voice: {voice_name}...")
        _kokoro_cache[lang] = KPipeline(lang_code=lang, repo_id='hexgrad/Kokoro-82M')
    return _kokoro_cache[lang]


def kokoro_to_wav(text, voice_id, speed, out_path, status_cb=None):
    import soundfile as sf
    pipeline = _get_pipeline(voice_id, status_cb=status_cb)
    chunks = []
    for _, _, audio in pipeline(text, voice=voice_id, speed=speed):
        chunks.append(audio)
    if not chunks:
        raise RuntimeError("Kokoro produced no audio.")
    combined = np.concatenate(chunks)
    sf.write(str(out_path), combined, 24000)
    return float(len(combined)) / 24000.0


# ─────────────────────────── TTS READER ───────────────────────────

def _split_sentences(text):
    pattern = re.compile(r'(?<=[.!?])\s+')
    parts = pattern.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


class TTSReader:
    def __init__(self, status_callback=None):
        self._playing = False
        self._paused = False
        self._stopped = False
        self._thread = None
        self._sentence_callback = None
        self._word_callback = None
        self._done_callback = None
        self._status_cb = status_callback
        self._sentence_idx = 0
        self._sentences = []
        self._pause_sentence_idx = 0
        self._pause_word_idx = 0
        self._resume_word_idx = 0
        self._text = ""
        self._current_audio = None
        self._current_word_boundaries = []
        self._current_word_idx = 0
        self._audio_dur = 0.0
        self._voice_id = ""
        self._speed = 1.0

    def set_callbacks(self, sentence_cb=None, done_cb=None, status_cb=None, word_cb=None):
        if sentence_cb: self._sentence_callback = sentence_cb
        if done_cb: self._done_callback = done_cb
        if status_cb: self._status_cb = status_cb
        if word_cb: self._word_callback = word_cb

    def _status(self, msg):
        if self._status_cb:
            self._status_cb(msg)

    def play(self, text, voice_id, speed, start_from=0):
        self.stop(block=True)
        self._playing = True
        self._paused = False
        self._stopped = False
        self._text = text
        self._voice_id = voice_id
        self._speed = speed
        self._current_word_idx = 0
        self._current_audio = None
        self._current_word_boundaries = []

        self._sentences = _split_sentences(text[start_from:]) if start_from < len(text) else _split_sentences(text)
        self._sentence_idx = 0
        self._pause_sentence_idx = 0
        self._pause_word_idx = 0
        self._resume_word_idx = 0

        if not self._sentences:
            self._status("No text to read")
            self._done()
            return

        self._thread = threading.Thread(
            target=self._play_thread, daemon=True
        )
        self._thread.start()

    def stop(self, block=False):
        if not self._playing:
            return
        self._stopped = True
        self._paused = False
        if self._thread and self._thread.is_alive() and block:
            self._thread.join(timeout=2)
        import sounddevice as sd
        sd.stop()
        self._playing = False

    def pause(self):
        if self._playing and not self._paused:
            self._paused = True
            self._pause_sentence_idx = self._sentence_idx
            self._pause_word_idx = self._current_word_idx
            import sounddevice as sd
            sd.stop()

    def resume(self):
        if self._playing and self._paused:
            self._paused = False
            self._sentence_idx = self._pause_sentence_idx
            self._current_word_idx = self._pause_word_idx

    @property
    def is_playing(self):
        return self._playing and not self._stopped

    @property
    def is_paused(self):
        return self._paused

    def set_word_idx(self, idx):
        self._current_word_idx = idx

    @property
    def paused_sentence_idx(self):
        return self._pause_sentence_idx

    @property
    def paused_word_idx(self):
        return self._resume_word_idx if self._resume_word_idx > 0 else self._pause_word_idx

    def _done(self):
        self._playing = False
        if self._done_callback:
            self._done_callback()

    def _play_thread(self):
        import sounddevice as sd
        self._last_pipeline = _get_pipeline(self._voice_id, status_cb=self._status_cb)
        self._last_pipeline_voice = self._voice_id
        while self._sentence_idx < len(self._sentences):
            if self._stopped:
                break

            sentence = self._sentences[self._sentence_idx]

            if self._sentence_callback:
                self._sentence_callback(self._sentence_idx, sentence)

            if self._voice_id != self._last_pipeline_voice:
                self._last_pipeline = _get_pipeline(self._voice_id, status_cb=self._status_cb)
                self._last_pipeline_voice = self._voice_id

            try:
                chunks = []
                for _, _, audio in self._last_pipeline(sentence, voice=self._voice_id, speed=self._speed):
                    chunks.append(audio)
                if not chunks:
                    self._sentence_idx += 1
                    continue
                combined = np.concatenate(chunks)
                if len(combined) == 0:
                    self._sentence_idx += 1
                    continue
                audio_dur = float(len(combined)) / 24000.0

            except Exception as e:
                if not self._stopped:
                    self._status(f"TTS error: {e}")
                break

            words = sentence.split()
            total_chars = sum(len(w) for w in words)
            if total_chars > 0 and len(words) > 0:
                boundaries = []
                running_samples = 0
                for w in words:
                    boundaries.append(running_samples)
                    running_samples += int(len(combined) * (len(w) / total_chars))
                boundaries.append(len(combined))
            else:
                boundaries = [0, len(combined)]
                words = [sentence]

            self._current_audio = combined
            self._current_word_boundaries = boundaries
            self._audio_dur = audio_dur

            start_word = 0
            if self._pause_word_idx > 0 and len(boundaries) > self._pause_word_idx:
                start_word = min(self._pause_word_idx, len(boundaries) - 2)
            self._current_word_idx = start_word
            self._resume_word_idx = start_word
            self._pause_word_idx = 0

            remaining_dur = audio_dur
            if start_word > 0 and start_word < len(boundaries):
                remaining_samples = len(combined) - boundaries[start_word]
                remaining_dur = float(remaining_samples) / 24000.0
            if self._word_callback:
                self._word_callback(sentence, remaining_dur)

            self._resume_word_idx = 0

            if start_word > 0 and start_word < len(boundaries):
                sample_start = boundaries[start_word]
                combined = combined[sample_start:]

            sd.play(combined, 24000)
            while sd.get_stream().active:
                if self._stopped or self._paused:
                    sd.stop()
                    break
                time.sleep(0.05)

            if self._stopped:
                break

            if self._paused:
                self._pause_sentence_idx = self._sentence_idx
                self._pause_word_idx = self._current_word_idx
                self._wait_pause()
                if self._stopped:
                    break
                continue

            self._sentence_idx += 1

        if not self._stopped:
            self._done()

    def _wait_pause(self):
        while self._paused and not self._stopped:
            time.sleep(0.1)

    def text_to_mp3(self, text, voice_id, speed, out_path):
        wav_path = Path(gettempdir()) / f"_tts_reader_{hash(text) % 1000000}.wav"
        try:
            kokoro_to_wav(text, voice_id, speed, str(wav_path), status_cb=self._status)
            subprocess.run([
                "ffmpeg", "-y", "-i", str(wav_path),
                "-codec:a", "libmp3lame", "-qscale:a", "2",
                str(out_path)
            ], capture_output=True, check=True)
            return True
        except Exception as e:
            self._status(f"MP3 conversion failed: {e}")
            return False
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass


_global_reader = None

def get_reader():
    global _global_reader
    if _global_reader is None:
        _global_reader = TTSReader()
    return _global_reader


# ─────────────────────────── DEPENDENCY CHECK ───────────────────────────

REQUIRED_PACKAGES = {
    "kokoro":        "kokoro",
    "numpy":         "numpy",
    "soundfile":     "soundfile",
    "sounddevice":   "sounddevice",
    "pillow":        "PIL",
}

OPTIONAL_PACKAGES = {
    "striprtf":      ("striprtf",       "RTF files (.rtf)"),
    "python-docx":   ("docx",           "Word documents (.docx)"),
    "odfpy":         ("odf",            "OpenDocument (.odt)"),
    "PyPDF2":        ("PyPDF2",         "PDF files (.pdf)"),
    "ebooklib":      ("ebooklib",       "E-books (.epub)"),
    "beautifulsoup4":("bs4",            "EPUB HTML parsing (ebooklib companion)"),
}

OPTIONAL_INFO = {
    "RTF files (.rtf)":
        "Rich Text Format — a plain-text-like document format. Supported since the '90s. "
        "Requires the 'striprtf' package (pip install striprtf).",
    "Word documents (.docx)":
        "Microsoft Word .docx format. Requires 'python-docx' (pip install python-docx). "
        "Extracts paragraph text only — no tables, headers, or images.",
    "OpenDocument (.odt)":
        "LibreOffice / OpenOffice .odt format. Requires 'odfpy' (pip install odfpy). "
        "Extracts paragraph text only.",
    "PDF files (.pdf)":
        "Portable Document Format. Requires 'PyPDF2' (pip install PyPDF2). "
        "Extracts text layer only — scanned/image PDFs will produce empty output.",
    "E-books (.epub)":
        "EPUB e-book format. Requires both 'ebooklib' and 'beautifulsoup4' "
        "(pip install ebooklib beautifulsoup4). Extracts body text from all chapters.",
    "EPUB HTML parsing (ebooklib companion)":
        "BeautifulSoup is needed alongside ebooklib to parse HTML content inside EPUB files. "
        "Install alongside ebooklib: pip install beautifulsoup4.",
}


def check_dependency(import_name):
    try:
        __import__(import_name)
        return True
    except ImportError:
        return False


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def check_all_dependencies():
    missing_required = []
    missing_optional = {}

    for pkg_name, import_name in REQUIRED_PACKAGES.items():
        if not check_dependency(import_name):
            missing_required.append(pkg_name)

    for pkg_name, (import_name, desc) in OPTIONAL_PACKAGES.items():
        if not check_dependency(import_name):
            missing_optional[pkg_name] = desc

    ffmpeg_ok = check_ffmpeg()

    return missing_required, missing_optional, ffmpeg_ok


def pip_install(*packages):
    pkg_list = " ".join(packages)
    cmd_line = f'start "Pip Install" cmd /k "pip install {pkg_list} && echo. && echo === Install complete! You can close this window. ==="'
    try:
        subprocess.Popen(cmd_line, shell=True)
        return True
    except Exception:
        return False


def show_required_dialog(missing_required, ffmpeg_ok):
    msgs = []

    if missing_required:
        pkgs = ", ".join(missing_required)
        msgs.append(f"REQUIRED packages missing:\n  {pkgs}")

    if not ffmpeg_ok:
        msgs.append("FFmpeg is not found on your system PATH.\n"
                    "File-to-MP3 conversion and some TTS may not work.\n"
                    "Download from: https://ffmpeg.org/download.html")

    if not msgs:
        return

    full_msg = "\n\n".join(msgs)

    if missing_required:
        full_msg += "\n\nInstall required packages now?"
        choice = messagebox.askyesno("Missing Required Dependencies", full_msg)
        if choice:
            pip_install(*missing_required)
    elif not ffmpeg_ok:
        messagebox.showwarning("Missing FFmpeg", full_msg)


# ─────────────────────────── GUI ───────────────────────────

class ReadSlopOutLoudApp:
    def __init__(self, missing_optional=None, ffmpeg_ok=True):
        self.root = Tk()
        self.root.title("Read Slop Out Loud")
        self.root.geometry("740x700")
        self.root.minsize(480, 380)
        self.root.configure(bg=DARK["BG"])

        self._missing_optional = missing_optional or {}
        self._ffmpeg_ok = ffmpeg_ok
        self._settings_open = False

        # State (must come before _build_ui)
        self._stopped_flag = False
        self._word_timer = None
        self._current_words = []
        self._word_index = 0
        self._word_positions = []
        self._prev_sent_start = 0
        self._highlight_tag = "word_hl"
        self._selected_file = None

        # Style
        self.style = ttk.Style()
        self._configure_style()

        # Build UI
        self._build_ui()

        # Init reader
        self._reader = get_reader()
        self._reader.set_callbacks(
            sentence_cb=self._on_sentence,
            word_cb=self._on_words,
            done_cb=self._on_done,
            status_cb=self._set_status
        )

        self._apply_theme()

    def _configure_style(self):
        self.style.theme_use("clam")

    def _apply_theme(self):
        t = THEME
        self.root.configure(bg=t["BG"])
        self.style.configure("TCombobox",
                             fieldbackground=t["COMBO_BG"],
                             background=t["BORDER"],
                             foreground=t["COMBO_FG"],
                             arrowcolor=t["COMBO_FG"],
                             selectbackground=t["ACCENT"],
                             selectforeground=t["FG"])
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", t["COMBO_BG"])],
                       foreground=[("readonly", t["COMBO_FG"])])

        # Rebuild UI cleanly
        for w in self.root.winfo_children():
            w.destroy()
        self._build_ui()
        self._reader.set_callbacks(
            sentence_cb=self._on_sentence,
            word_cb=self._on_words,
            done_cb=self._on_done,
            status_cb=self._set_status
        )

    def _c(self, key):
        return THEME[key]

    def _build_ui(self):
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        main = Frame(self.root, bg=self._c("BG"))
        main.grid(row=0, column=0, sticky=NSEW)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        # ── Header ──
        header = Frame(main, bg=self._c("PANEL"))
        header.grid(row=0, column=0, sticky=EW)

        Label(header, text="  Read Slop Out Loud  ",
              bg=self._c("PANEL"), fg=self._c("FG"),
              font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky=W, pady=8, padx=8)

        self._settings_toggle_btn = Button(header, text="Settings", bg=self._c("INPUT"),
                                            fg=self._c("FG2"), relief="flat",
                                            font=("Segoe UI", 9), cursor="hand2",
                                            command=self._toggle_settings, width=12)
        self._settings_toggle_btn.grid(row=0, column=1, sticky=E, padx=8, pady=8)

        # ── Controls ──
        ctrl = Frame(main, bg=self._c("BG"))
        ctrl.grid(row=1, column=0, sticky=EW, padx=12, pady=(8, 0))
        ctrl.columnconfigure(0, weight=1)

        # Voice
        voice_row = Frame(ctrl, bg=self._c("BG"))
        voice_row.pack(fill="x")
        Label(voice_row, text="Kokoro Voice:", bg=self._c("BG"), fg=self._c("FG2"),
              font=("Segoe UI", 9)).pack(side=LEFT)
        self._voice_var = StringVar(value=list(VOICES.keys())[0])
        self._voice_combo = ttk.Combobox(voice_row, textvariable=self._voice_var,
                                          values=list(VOICES.keys()), state="readonly",
                                          font=("Segoe UI", 10))
        self._voice_combo.pack(side=LEFT, padx=(4, 0), fill="x", expand=True)

        # Speed
        speed_row = Frame(ctrl, bg=self._c("BG"))
        speed_row.pack(fill="x", pady=(6, 0))
        Label(speed_row, text="Speed:", bg=self._c("BG"), fg=self._c("FG2"),
              font=("Segoe UI", 9)).pack(side=LEFT)
        self._speed_var = DoubleVar(value=1.0)
        self._speed_lbl = Label(speed_row, text="1.0x", bg=self._c("BG"),
                                 fg=self._c("ACCENT"), font=("Segoe UI", 9, "bold"))
        self._speed_lbl.pack(side=LEFT, padx=2)
        Scale(speed_row, variable=self._speed_var, from_=0.5, to=2.5, resolution=0.05,
              orient=HORIZONTAL, bg=self._c("BG"), fg=self._c("FG"),
              troughcolor=self._c("INPUT"), activebackground=self._c("ACCENT"),
              highlightthickness=1, highlightbackground=self._c("BORDER"),
              sliderrelief="raised", bd=1, sliderlength=20, showvalue=0,
              command=lambda v: self._speed_lbl.config(text=f"{float(v):.2f}x")).pack(
              side=LEFT, fill="x", expand=True, padx=(4, 0))

        # Buttons
        btn_row = Frame(ctrl, bg=self._c("BG"))
        btn_row.pack(fill="x", pady=(8, 0))
        self._play_btn = Button(btn_row, text="Play", bg=self._c("ACCENT"), fg=self._c("FG"),
                                 relief="flat", font=("Segoe UI", 9), cursor="hand2",
                                 command=self._play, width=8)
        self._play_btn.pack(side=LEFT, padx=(0, 4))
        self._pause_btn = Button(btn_row, text="Pause", bg=self._c("INPUT"), fg=self._c("FG2"),
                                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                                  command=self._pause, width=8)
        self._pause_btn.pack(side=LEFT, padx=2)
        self._stop_btn = Button(btn_row, text="Stop", bg=self._c("INPUT"), fg=self._c("FG2"),
                                 relief="flat", font=("Segoe UI", 9), cursor="hand2",
                                 command=self._stop, width=8)
        self._stop_btn.pack(side=LEFT, padx=2)
        self._paste_btn = Button(btn_row, text="Paste", bg=self._c("INPUT"), fg=self._c("FG2"),
                                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                                  command=self._paste, width=8)
        self._paste_btn.pack(side=LEFT, padx=2)
        self._clear_btn = Button(btn_row, text="Clear", bg=self._c("INPUT"), fg=self._c("FG2"),
                                  relief="flat", font=("Segoe UI", 9), cursor="hand2",
                                  command=self._clear, width=8)
        self._clear_btn.pack(side=LEFT, padx=2)
        self._status_lbl = Label(btn_row, text="", bg=self._c("BG"), fg=self._c("FG3"),
                                  font=("Segoe UI", 8, "italic"))
        self._status_lbl.pack(side=LEFT, padx=(8, 0))

        # Text area
        text_frame = Frame(main, bg=self._c("BG"))
        text_frame.grid(row=2, column=0, sticky=NSEW, padx=12, pady=(8, 0))
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        self._text = Text(text_frame, height=12, bg=self._c("INPUT"), fg=self._c("FG"),
                           insertbackground=self._c("FG"), relief="flat",
                           font=("Segoe UI", 10), wrap="word",
                           highlightthickness=1, highlightcolor=self._c("ACCENT"),
                           highlightbackground=self._c("BORDER"), padx=6, pady=4,
                           undo=True)
        self._text.grid(row=0, column=0, sticky="nsew")
        scrollbar = Scrollbar(text_frame, command=self._text.yview,
                              bg=self._c("PANEL"), troughcolor=self._c("BG"))
        scrollbar.grid(row=0, column=1, sticky="ns")
        self._text.config(yscrollcommand=scrollbar.set)
        self._text.bind("<Button-1>", self._on_text_click)

        # Right-click context menu
        self._right_click_menu = Menu(self.root, tearoff=0,
                                       bg=self._c("INPUT"), fg=self._c("FG"),
                                       activebackground=self._c("ACCENT"),
                                       activeforeground=self._c("FG"),
                                       font=("Segoe UI", 9))
        self._right_click_menu.add_command(label="Undo", accelerator="Ctrl+Z",
                                            command=self._text_undo)
        self._right_click_menu.add_command(label="Redo", accelerator="Ctrl+Y",
                                            command=self._text_redo)
        self._right_click_menu.add_separator()
        self._right_click_menu.add_command(label="Cut", accelerator="Ctrl+X",
                                            command=self._text_cut)
        self._right_click_menu.add_command(label="Copy", accelerator="Ctrl+C",
                                            command=self._text_copy)
        self._right_click_menu.add_command(label="Paste", accelerator="Ctrl+V",
                                            command=self._text_paste)
        self._right_click_menu.add_separator()
        self._right_click_menu.add_command(label="Select All", accelerator="Ctrl+A",
                                            command=self._text_select_all)
        self._text.bind("<Button-3>", self._show_right_click_menu)
        self._text.bind("<Button-2>", self._show_right_click_menu)

        # Resize handle at bottom of text area
        self._resize_handle = Frame(main, bg=self._c("BORDER"), height=6, cursor="sb_v_double_arrow")
        self._resize_handle.grid(row=3, column=0, sticky=EW, padx=12, pady=(0, 0))
        self._resize_handle.bind("<Button-1>", self._start_resize)
        self._resize_handle.bind("<B1-Motion>", self._on_resize)
        self._resize_start_y = 0
        self._resize_start_h = 0

        self._text.tag_configure(self._highlight_tag,
                                  background=THEME["HIGHLIGHT_BG"],
                                  foreground=THEME["HIGHLIGHT_FG"])

        # ── Settings panel (collapsible) ──
        self._settings_frame = Frame(main, bg=self._c("PANEL"))
        self._settings_frame.grid(row=4, column=0, sticky=EW, padx=12, pady=(4, 4))
        self._build_settings_content()
        if not self._settings_open:
            self._settings_frame.grid_remove()

        # ── File-to-MP3 section ──
        export_row = Frame(main, bg=self._c("BG"))
        export_row.grid(row=5, column=0, sticky=EW, padx=12, pady=(2, 4))

        Label(export_row, text="Convert file to MP3:", bg=self._c("BG"), fg=self._c("FG2"),
              font=("Segoe UI", 9)).grid(row=0, column=0, sticky=W)

        exp_ctrl = Frame(export_row, bg=self._c("BG"))
        exp_ctrl.grid(row=1, column=0, sticky=EW, pady=(4, 0))

        self._convert_btn = Button(exp_ctrl, text="Convert", bg=self._c("ACCENT"),
                                    fg=self._c("FG"), relief="flat", font=("Segoe UI", 9),
                                    cursor="hand2", command=self._convert_selected)
        self._convert_btn.pack(side=LEFT, padx=(0, 6))
        self._open_folder_btn = Button(exp_ctrl, text="Go to MP3", bg=self._c("INPUT"),
                                        fg=self._c("FG2"), relief="flat",
                                        font=("Segoe UI", 9), cursor="hand2",
                                        command=self._open_output_folder)
        self._open_folder_btn.pack(side=LEFT, padx=(0, 6))
        Button(exp_ctrl, text="Select File", bg=self._c("INPUT"), fg=self._c("FG2"),
               relief="flat", font=("Segoe UI", 9), cursor="hand2",
               command=self._browse_file).pack(side=LEFT, padx=(0, 6))
        self._file_name_lbl = Label(exp_ctrl, text="", bg=self._c("BG"), fg=self._c("FG"),
                                     font=("Segoe UI", 9), anchor="w")
        self._file_name_lbl.pack(side=LEFT, padx=(0, 6))
        self._convert_status_lbl = Label(exp_ctrl, text="", bg=self._c("BG"),
                                          fg=self._c("WARN_COL"),
                                          font=("Segoe UI", 8, "italic"))
        self._convert_status_lbl.pack(side=LEFT, padx=(0, 0))

    def _build_settings_content(self):
        for w in self._settings_frame.winfo_children():
            w.destroy()

        self._settings_frame.columnconfigure(1, weight=1)

        # Row 0: Theme toggle + Refresh
        if THEME == DARK:
            theme_label = "Gay Mode"
            theme_btn_bg = "#FFB7C5"
            theme_btn_fg = "#A2646F"
        else:
            theme_label = "Dark Mode"
            theme_btn_bg = self._c("INPUT")
            theme_btn_fg = self._c("FG2")
        Button(self._settings_frame, text=theme_label,
               bg=theme_btn_bg, fg=theme_btn_fg,
               relief="flat", font=("Segoe UI", 9), cursor="hand2",
               command=self._toggle_theme, width=14).grid(
               row=0, column=0, sticky=W, padx=6, pady=(6, 0))
        Label(self._settings_frame, text="Switch between dark and light theme",
              bg=self._c("PANEL"), fg=self._c("FG3"),
              font=("Segoe UI", 8)).grid(row=0, column=1, sticky=W, padx=(6, 0), pady=(6, 0))
        Button(self._settings_frame, text="Refresh",
               bg=self._c("ACCENT"), fg=self._c("FG"),
               relief="flat", font=("Segoe UI", 8), cursor="hand2",
               command=self._refresh_settings, width=10).grid(
               row=0, column=2, sticky=E, padx=6, pady=(6, 0))

        # Row 1: FFmpeg status
        ffmpeg_text = "FFmpeg: Available" if self._ffmpeg_ok else "FFmpeg: NOT FOUND (MP3 conversion disabled)"
        ffmpeg_color = self._c("OK_COL") if self._ffmpeg_ok else self._c("ERR_COL")
        Label(self._settings_frame, text=ffmpeg_text,
              bg=self._c("PANEL"), fg=ffmpeg_color,
              font=("Segoe UI", 9)).grid(row=1, column=0, sticky=W, padx=6, pady=(6, 0))
        if not self._ffmpeg_ok:
            Label(self._settings_frame,
                  text="Download from ffmpeg.org and add to PATH",
                  bg=self._c("PANEL"), fg=self._c("FG3"),
                  font=("Segoe UI", 8)).grid(row=1, column=1, sticky=W, padx=(6, 0), pady=(6, 0))

        # Rows for each optional package
        r = 2
        optional_order = [
            ("striprtf",       "RTF files (.rtf)"),
            ("python-docx",    "Word documents (.docx)"),
            ("odfpy",          "OpenDocument (.odt)"),
            ("PyPDF2",         "PDF files (.pdf)"),
            ("ebooklib",       "E-books (.epub)"),
            ("beautifulsoup4", "EPUB HTML parsing (ebooklib companion)"),
        ]
        for pkg_name, desc in optional_order:
            installed = pkg_name not in self._missing_optional
            status_text = "Installed" if installed else "Not installed"
            status_col = self._c("OK_COL") if installed else self._c("WARN_COL")

            row_frame = Frame(self._settings_frame, bg=self._c("PANEL"))
            row_frame.grid(row=r, column=0, columnspan=2, sticky=EW, padx=2, pady=1)
            row_frame.columnconfigure(1, weight=1)

            Label(row_frame, text=f"  {desc}", bg=self._c("PANEL"), fg=self._c("FG2"),
                  font=("Segoe UI", 9)).grid(row=0, column=0, sticky=W, padx=(6, 0))

            Label(row_frame, text=status_text, bg=self._c("PANEL"),
                  fg=status_col if installed else PURPLE_ACCENT,
                  font=("Segoe UI", 9)).grid(row=0, column=1, sticky=W, padx=(8, 0))

            if not installed:
                install_btn = Button(row_frame, text="Install",
                                     bg=self._c("INPUT"), fg=self._c("FG2"),
                                     relief="flat", font=("Segoe UI", 8),
                                     cursor="hand2",
                                     command=lambda p=pkg_name: pip_install(p))
                install_btn.grid(row=0, column=1, sticky=E, padx=(0, 4))

            help_btn = Button(row_frame, text="?",
                              bg=self._c("INPUT"), fg=self._c("FG2"),
                              relief="flat", font=("Segoe UI", 8, "bold"),
                              cursor="hand2",
                              command=lambda d=desc: self._show_optional_info(d))
            help_btn.grid(row=0, column=2, sticky=E, padx=(0, 4))
            r += 1

    def _show_optional_info(self, desc):
        info = OPTIONAL_INFO.get(desc, "No additional info available.")
        Toplevel_info = Toplevel(self.root)
        Toplevel_info.title("File Format Info")
        Toplevel_info.configure(bg=self._c("PANEL"))
        Toplevel_info.geometry("450x250")
        Toplevel_info.transient(self.root)
        Toplevel_info.grab_set()

        title_lbl = Label(Toplevel_info, text=desc, bg=self._c("PANEL"),
                          fg=self._c("FG"), font=("Segoe UI", 11, "bold"),
                          wraplength=410, justify=LEFT)
        title_lbl.pack(padx=16, pady=(12, 6), anchor=W)

        info_lbl = Label(Toplevel_info, text=info, bg=self._c("PANEL"),
                         fg=self._c("FG2"), font=("Segoe UI", 9),
                         wraplength=420, justify=LEFT)
        info_lbl.pack(padx=16, pady=(0, 6), anchor=W)

        ok_btn = Button(Toplevel_info, text="OK", bg=self._c("ACCENT"), fg=self._c("FG"),
                        relief="flat", font=("Segoe UI", 9), cursor="hand2",
                        command=Toplevel_info.destroy)
        ok_btn.pack(pady=(4, 10))

    def _toggle_settings(self):
        if self._settings_open:
            self._settings_frame.grid_remove()
            self._settings_open = False
        else:
            self._settings_frame.grid()
            self._settings_open = True

    def _refresh_settings(self):
        self._missing_optional = {
            pkg: import_name
            for pkg, import_name in [
                (pkg, import_name)
                for pkg, (import_name, _) in OPTIONAL_PACKAGES.items()
            ]
            if not check_dependency(import_name)
        }
        self._ffmpeg_ok = check_ffmpeg()
        self._build_settings_content()

    def _toggle_theme(self):
        global THEME
        if THEME == DARK:
            THEME = LIGHT
            _save_theme_setting("gay")
        else:
            THEME = DARK
            _save_theme_setting("dark")
        self._apply_theme()


    def _set_status(self, msg):
        self._status_lbl.config(text=msg)

    def _on_text_click(self, event):
        self._click_pos = self._text.index(f"@{event.x},{event.y}")

    def _paste(self):
        try:
            text = self.root.clipboard_get()
            if text:
                self._text.insert(INSERT, text)
        except Exception:
            pass

    def _clear(self):
        self._text.delete("1.0", END)

    # ── Right-click / keyboard undo/redo/cut/copy/paste ──

    def _show_right_click_menu(self, event):
        try:
            self._right_click_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._right_click_menu.grab_release()

    def _text_undo(self):
        try:
            self._text.edit_undo()
        except Exception:
            pass

    def _text_redo(self):
        try:
            self._text.edit_redo()
        except Exception:
            pass

    def _text_cut(self):
        try:
            self._text.event_generate("<<Cut>>")
        except Exception:
            pass

    def _text_copy(self):
        try:
            self._text.event_generate("<<Copy>>")
        except Exception:
            pass

    def _text_paste(self):
        try:
            self._text.event_generate("<<Paste>>")
        except Exception:
            pass

    def _text_select_all(self):
        self._text.tag_add("sel", "1.0", END)
        self._text.mark_set(INSERT, END)
        return "break"

    # ── Resize text area by dragging ──

    def _start_resize(self, event):
        self._resize_start_y = event.y_root
        self._resize_start_h = self._text.winfo_height()

    def _on_resize(self, event):
        delta = event.y_root - self._resize_start_y
        new_h = self._resize_start_h + delta
        if new_h < 60:
            new_h = 60
        self._text.config(height=new_h)

    def _play(self):
        text = self._text.get("1.0", END).strip()
        if not text:
            self._set_status("No text to read")
            return

        self._stopped_flag = False
        start_idx = 0
        try:
            cursor = self._text.index(INSERT)
            if cursor != "1.0":
                cp = self._text.count("1.0", cursor)
                if cp[0] <= 1 or cp[0] >= len(text):
                    start_idx = 0
                    self._text.mark_set(INSERT, "1.0")
                else:
                    start_idx = cp[0] - 1
        except Exception:
            start_idx = 0

        if start_idx < 0 or start_idx >= len(text):
            start_idx = 0

        voice_key = self._voice_var.get()
        voice_id = VOICES.get(voice_key, voice_key)
        speed = float(self._speed_var.get())

        self._reader.set_callbacks(
            sentence_cb=self._on_sentence,
            word_cb=self._on_words,
            done_cb=self._on_done,
            status_cb=self._set_status
        )

        self._play_btn.config(state=DISABLED, bg=self._c("INPUT"))
        self._pause_btn.config(text="Pause", bg=self._c("INPUT"), fg=self._c("FG2"))
        self._stop_btn.config(bg=self._c("ACCENT"), fg=self._c("FG"))
        self._set_status("Reading...")
        self._reader.play(text, voice_id, speed, start_from=start_idx)
        self._poll_playback()

    def _pause(self):
        if self._reader.is_paused:
            self._reader.resume()
            self._stopped_flag = False
            self._pause_btn.config(text="Pause")
            self._set_status("Reading...")
            self._poll_playback()
        else:
            self._reader.pause()
            self._cancel_word_timer()
            self._clear_highlight()
            self._pause_btn.config(text="Resume")
            self._set_status("Paused")

    def _stop(self):
        self._stopped_flag = True
        self._reader.stop()
        self._cancel_word_timer()
        self._reset_ui()

    def _reset_ui(self):
        self._stopped_flag = False
        self._play_btn.config(state=NORMAL, bg=self._c("ACCENT"))
        self._pause_btn.config(text="Pause", bg=self._c("INPUT"), fg=self._c("FG2"))
        self._stop_btn.config(bg=self._c("INPUT"), fg=self._c("FG2"))
        self._set_status("")
        self._cancel_word_timer()
        self._clear_highlight()

    def _on_sentence(self, idx, sentence):
        self._clear_highlight()
        self._cancel_word_timer()
        text = self._text.get("1.0", END)
        search_from = 0
        for i in range(idx):
            s = self._reader._sentences[i] if i < len(self._reader._sentences) else sentence
            pos = text.find(_first_words(s, 1), search_from)
            if pos == -1:
                return
            search_from = pos + 1

        pos = text.find(sentence, search_from)
        if pos == -1:
            pos = text.find(_first_words(sentence, 8), search_from)
        if pos == -1:
            pos = text.find(_first_words(sentence, 4), search_from)
        if pos == -1:
            return

        self._prev_sent_start = pos

    def _on_words(self, sentence, audio_dur):
        self._clear_highlight()
        text = self._text.get("1.0", END)
        char_offset = self._prev_sent_start

        pos = text.find(sentence, char_offset)
        if pos == -1:
            pos = text.find(_first_words(sentence, 8), char_offset)
        if pos == -1:
            pos = text.find(_first_words(sentence, 4), char_offset)
        if pos == -1:
            return
        char_offset = pos

        words = sentence.split()
        if not words:
            return

        start_word = self._reader.paused_word_idx
        if start_word < 0 or start_word >= len(words):
            start_word = 0

        word_positions = []
        sig_pos = char_offset
        for wi, w in enumerate(words):
            wpos = text.find(w, sig_pos)
            if wpos == -1:
                wpos = sig_pos
            word_positions.append(wpos)
            sig_pos = wpos + len(w)

        remaining_words = words[start_word:]
        total_chars = sum(len(w) for w in remaining_words)
        if total_chars == 0:
            total_chars = sum(len(w) for w in words)
        interval_ms = int((audio_dur / max(1, total_chars)) * 1000)

        self._word_positions = word_positions
        self._current_words = words
        self._word_index = 0

        def highlight_next(i):
            self._clear_highlight()
            if self._stopped_flag:
                return
            if self._reader.is_paused:
                return
            if i >= len(word_positions):
                return
            wpos = word_positions[i]
            w = words[i]
            if wpos >= 0 and w:
                start_tk = self._text.index(f"1.0 + {wpos} chars")
                end_tk = self._text.index(f"1.0 + {wpos + len(w)} chars")
                self._text.tag_add(self._highlight_tag, start_tk, end_tk)
                self._text.see(start_tk)
            self._reader.set_word_idx(i)
            next_i = i + 1
            if next_i < len(word_positions):
                delay = max(1, int(interval_ms * len(w)))
                self._word_timer = self.root.after(delay, lambda: highlight_next(next_i))

        highlight_next(start_word)

    def _cancel_word_timer(self):
        if self._word_timer:
            self.root.after_cancel(self._word_timer)
            self._word_timer = None

    def _clear_highlight(self):
        self._cancel_word_timer()
        self._text.tag_remove(self._highlight_tag, "1.0", END)

    def _on_done(self):
        self._reset_ui()

    def _poll_playback(self):
        if self._reader.is_paused:
            self.root.after(200, self._poll_playback)
            return
        if self._reader.is_playing:
            self.root.after(200, self._poll_playback)
        else:
            if not self._stopped_flag:
                self._reset_ui()

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select text file to convert to MP3",
            filetypes=[
                ("Text / Doc files", "*.txt *.rtf *.md *.rst *.log *.csv *.json *.xml *.html *.htm *.srt *.vtt *.sbv *.sub *.ass *.ssa"),
                ("Word documents", "*.docx *.odt"),
                ("PDF files", "*.pdf"),
                ("E-book", "*.epub"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        self._selected_file = Path(path)
        self._file_name_lbl.config(text=self._selected_file.name)
        self._convert_status_lbl.config(text="")

    def _convert_selected(self):
        if not self._selected_file:
            return
        text = self._extract_text_from_file(self._selected_file)
        if text is None:
            return

        if not text.strip():
            self._convert_status_lbl.config(text="File is empty")
            return

        out_dir = Path.cwd() / "output"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / self._selected_file.with_suffix(".mp3").name
        voice_key = self._voice_var.get()
        voice_id = VOICES.get(voice_key, voice_key)
        speed = float(self._speed_var.get())

        self._convert_status_lbl.config(text="Converting...")
        self.root.update()
        success = self._reader.text_to_mp3(text, voice_id, speed, str(out_path))
        if success:
            self._last_mp3 = str(out_path)
            self._convert_status_lbl.config(text=f"Saved: {out_path.name}")
        else:
            self._convert_status_lbl.config(text="Conversion failed")

    def _extract_text_from_file(self, path):
        suffix = path.suffix.lower()
        try:
            if suffix == ".rtf":
                from striprtf.striprtf import rtf_to_text
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    return rtf_to_text(fh.read())
            elif suffix == ".docx":
                from docx import Document
                doc = Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs if p.text)
            elif suffix == ".odt":
                from odf.opendocument import load as odf_load
                from odf.text import P
                from odf import teletype
                doc = odf_load(str(path))
                return "\n".join(
                    teletype.extractText(p) for p in doc.getElementsByType(P)
                    if teletype.extractText(p).strip()
                )
            elif suffix == ".pdf":
                from PyPDF2 import PdfReader
                reader = PdfReader(str(path))
                return "\n".join(page.extract_text() or "" for page in reader.pages)
            elif suffix == ".epub":
                from ebooklib import epub
                from bs4 import BeautifulSoup
                book = epub.read_epub(str(path))
                parts = []
                for item in book.get_items_of_type(9):
                    soup = BeautifulSoup(item.get_body_content(), "html.parser")
                    parts.append(soup.get_text())
                return "\n".join(parts)
            elif suffix in (".html", ".htm", ".srt", ".vtt", ".sbv", ".sub", ".ass",
                            ".ssa", ".md", ".rst", ".log", ".csv", ".json", ".xml"):
                return path.read_text(encoding="utf-8", errors="replace")
            else:
                return path.read_text(encoding="utf-8", errors="replace")
        except ImportError as e:
            lib = str(e).rsplit(" ", 1)[-1].replace("'", "").replace('"', "")
            pkg_map = {
                "docx": "python-docx",
                "odf": "odfpy",
                "PyPDF2": "PyPDF2",
                "ebooklib": "ebooklib",
                "bs4": "beautifulsoup4",
                "striprtf": "striprtf",
            }
            pkg = pkg_map.get(lib, lib)
            self._convert_status_lbl.config(text=f"Missing library: pip install {pkg}")
            if messagebox.askyesno("Missing Library",
                                    f"'{pkg}' is required to read this file type.\n\n"
                                    f"Install it now with: pip install {pkg}?",
                                    parent=self.root):
                pip_install(pkg)
            return None
        except Exception as e:
            self._convert_status_lbl.config(text=f"Read error: {e}")
            return None

    def _open_output_folder(self):
        out_dir = Path.cwd() / "output"
        out_dir.mkdir(exist_ok=True)
        if hasattr(self, '_last_mp3') and self._last_mp3:
            os.startfile(str(Path(self._last_mp3).parent))
        elif out_dir.exists():
            os.startfile(str(out_dir))

    def run(self):
        self.root.mainloop()


def _first_words(text, n):
    words = text.split()
    return " ".join(words[:n])


# ─────────────────────────── ENTRY POINT ───────────────────────────

def main():
    missing_req, missing_opt, ffmpeg_ok = check_all_dependencies()

    if missing_req or not ffmpeg_ok:
        show_required_dialog(missing_req, ffmpeg_ok)

    app = ReadSlopOutLoudApp(missing_optional=missing_opt, ffmpeg_ok=ffmpeg_ok)
    app.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        crash_log = Path(__file__).with_name("crash.log")
        with open(crash_log, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"CRASH [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(f"Python: {sys.executable}\n")
            f.write(f"{'='*60}\n")
            traceback.print_exc(file=f)
        print(f"\nCRASH! Details written to: {crash_log}", file=sys.stderr)
        sys.exit(1)
