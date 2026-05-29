# Read Slop Out Loud

**Desktop TTS Reader** — paste text, choose a Kokoro AI voice, and hear it spoken aloud with synchronized word-by-word highlighting. Convert any supported document directly to MP3.

Built with Python + Tkinter. Uses the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) neural TTS model (runs locally — no cloud API, no internet required after first model download).

---

## Features

- **Real-time TTS playback** with per-word text highlighting as each word is spoken
- **Sentence-level navigation** — playback pauses/resumes at sentence boundaries
- **28 built-in voices** (14 American + 6 British; male & female). See [Voice list](#voice-list) below
- **Adjustable speed** (0.5–2.5×) via slider
- **Play from cursor** — click anywhere in your text and playback starts from that point
- **File-to-MP3 conversion** — convert entire documents to MP3 with a single click
- **Resizable text area** — drag the handle below the text box to expand
- **Right-click context menu** with Undo/Redo/Cut/Copy/Paste/Select All
- **Crash logging** — unexpected errors are written to `crash.log`
- **Two color themes** — Dark mode (default) and Light mode (gay mode)

### Supported input formats for MP3 conversion

| Format                                              | Required package |
| --------------------------------------------------- | ---------------- |
| Plain text (`.txt`, `.md`, `.rst`, `.log`, `.csv`, `.json`, `.xml`, `.html`, `.htm`) | None (built-in) |
| Subtitle files (`.srt`, `.vtt`, `.sbv`, `.sub`, `.ass`, `.ssa`) | None (built-in) |
| MS Word (`.docx`)                                   | `python-docx`    |
| OpenDocument (`.odt`)                               | `odfpy`          |
| PDF (`.pdf`)                                        | `PyPDF2`         |
| Rich Text Format (`.rtf`)                           | `striprtf`       |
| E-book (`.epub`)                                    | `ebooklib` + `beautifulsoup4` |

*PDF support is text-layer only. Scanned/image PDFs will produce empty output.*

---

## Requirements

### System

- **Windows** (tested), macOS, or Linux
- **Python 3.10–3.12** (Python 3.13 is not yet supported by Kokoro)
- **FFmpeg** — required for MP3 conversion. [Download here](https://ffmpeg.org/download.html) and ensure `ffmpeg` is on your system PATH (i.e., typing `ffmpeg -version` in a terminal works).
- **espeak-ng** — recommended for best pronunciation (especially non-English fallback). [Download for Windows](https://github.com/espeak-ng/espeak-ng/releases).

### Python packages

#### Required (auto-installed on first launch)

| Package      | Purpose                         |
| ------------ | ------------------------------- |
| `kokoro`     | Kokoro-82M neural TTS engine    |
| `numpy`      | Audio buffer arrays             |
| `soundfile`  | WAV file read/write             |
| `sounddevice`| Real-time audio playback        |
| `Pillow`     | Image handling (Tkinter dependency) |

`kokoro` also pulls in these automatically:
- `torch` (PyTorch — CPU-only by default; ~2 GB download)
- `transformers`
- `huggingface-hub`
- `misaki[en]` (English text processing)

#### Optional (for extended file format support)

| Package           | Enables                     | Install command                      |
| ----------------- | --------------------------- | ------------------------------------ |
| `python-docx`     | `.docx` Word documents      | `pip install python-docx`            |
| `odfpy`           | `.odt` OpenDocument files   | `pip install odfpy`                  |
| `PyPDF2`          | `.pdf` PDF files            | `pip install PyPDF2`                 |
| `striprtf`        | `.rtf` Rich Text Format     | `pip install striprtf`               |
| `ebooklib`        | `.epub` E-books             | `pip install ebooklib beautifulsoup4` |
| `beautifulsoup4`  | EPUB HTML parsing           | *(paired with ebooklib above)*       |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/necrokittie/ReadSlopOutLoud.git
cd ReadSlopOutLoud

# 2. (Recommended) Create a virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install required packages
pip install kokoro numpy soundfile sounddevice Pillow

# 4. Install FFmpeg (see Requirements above) and ensure it's on your PATH

# 5. (Optional) Install any document format packages you need
pip install python-docx PyPDF2 striprtf ebooklib beautifulsoup4
```

> **Note:** The first time you run the app, Kokoro will download the ~82 MB model from HuggingFace Hub. This is a one-time download and the model is cached locally.

---

## Usage

### Windows

Double-click `Read Slop Out Loud.bat`, or run from a terminal:

```powershell
python read_slop_out_loud.py
```

### macOS / Linux

```bash
python read_slop_out_loud.py
```

### Quick start

1. **Paste or type text** into the main text area (or use the **Paste** button)
2. **Choose a voice** from the dropdown (28 voices available)
3. **Adjust speed** with the slider (0.5× to 2.5×)
4. Click **Play** — each word highlights as it's spoken
5. Click anywhere in the text and hit Play to **start from that position**
6. Use **Pause** / **Stop** as needed

### File-to-MP3

1. Click **Select File** and pick any supported document
2. Click **Convert** — the app extracts all text and synthesizes an MP3
3. MP3s are saved to an `output/` folder in the app directory
4. Click **Go to MP3** to open the output folder

### Settings panel

Click the **Settings** button to:
- Toggle between **Dark mode** and **Light mode** (persisted across launches)
- See **FFmpeg status** — green if available, red with download link if not
- See **optional package status** with one-click install buttons for each
- Click the **Refresh** button to re-detect installed packages after manual pip installs

---

## Voice List

### American Male
| Voice ID    | Description              |
| ----------- | ------------------------ |
| `am_adam`   | Deep American Male (default) |
| `am_michael`| Warm American Male       |
| `am_fenrir` | Gruff Intense Male       |
| `am_puck`   | Light Quick Male         |
| `am_echo`   | Clear Measured Male      |
| `am_eric`   | Steady Composed Male     |
| `am_liam`   | Younger American Male    |
| `am_onyx`   | Rich Authoritative Male  |

### British Male
| Voice ID    | Description              |
| ----------- | ------------------------ |
| `bm_george` | Composed British Male    |
| `bm_lewis`  | Intense British Male     |
| `bm_daniel` | Neutral British Male     |
| `bm_fable`  | Storyteller British Male |

### American Female
| Voice ID    | Description              |
| ----------- | ------------------------ |
| `af_heart`  | Warm American Female     |
| `af_bella`  | Expressive American Female |
| `af_nicole` | Smooth American Female   |
| `af_aoede`  | Dramatic American Female |
| `af_kore`   | Cool American Female     |
| `af_sarah`  | Natural American Female  |
| `af_nova`   | Strong American Female   |
| `af_sky`    | Airy American Female     |
| `af_jessica`| Engaging American Female |
| `af_river`  | Calm American Female     |

### British Female
| Voice ID    | Description              |
| ----------- | ------------------------ |
| `bf_emma`   | Authoritative British Female |
| `bf_isabella`| Elegant British Female  |
| `bf_alice`  | Warm British Female      |
| `bf_lily`   | Gentle British Female    |

---

## How It Works

1. **Text is split into sentences** on `.`, `!`, and `?` boundaries
2. Each sentence is fed to the **Kokoro-82M model** (a StyleTTS 2-based neural TTS running entirely on your local machine)
3. Audio is played in real-time via **sounddevice** (PortAudio)
4. Word boundaries are estimated by character-length heuristics and displayed as **per-word highlighting** in the text area
5. For file conversion, text is extracted from the document, synthesized to a temporary WAV, then transcoded to **MP3** via **FFmpeg**

No audio or text ever leaves your machine.

---

## Troubleshooting

### App won't start / crashes immediately

- Check `crash.log` in the app folder for details
- Ensure you're using **Python 3.10–3.12** (Python 3.13 is not yet supported)
- Run the install commands again: `pip install kokoro numpy soundfile sounddevice Pillow`

### "No audio device" or no sound

- Check that your speakers/headphones are connected and not muted
- On Linux, install PortAudio: `sudo apt install libportaudio2`

### "FFmpeg not found" when converting to MP3

- Install FFmpeg from [ffmpeg.org](https://ffmpeg.org/download.html)
- Verify with: `ffmpeg -version`
- On Windows, you may need to add FFmpeg's `bin/` folder to your system PATH

### Model download fails

- The Kokoro-82M model (~82 MB) requires internet on first run
- If behind a proxy, set `HF_ENDPOINT=https://hf-mirror.com` for a mirror
- The model is cached in HuggingFace Hub's default cache directory

### Slow performance / high CPU usage

- Kokoro runs on CPU by default. This is expected — neural TTS is computationally intensive
- Consider installing PyTorch with CUDA if you have an NVIDIA GPU, though Kokoro-82M is small enough that CPU inference is adequate for most use cases

---

## License

This project is provided as-is. The Kokoro-82M model is distributed under the [Apache 2.0 license](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/LICENSE). See the model page for details.

---

## Credits

- **TTS engine:** [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad
- **Originally extracted** from [Sloppa Engine 9000](https://github.com/necrokittie/Sloppa-Engine-9000)
