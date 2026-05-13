# 8D Audio Studio

A fully local, offline-capable desktop audio studio built in Python.
Create, sample, and arrange music — then render it in 8D binaural or wide stereo spatial mode.

---

## Requirements

- **Windows 10 or 11**
- **Python 3.11 or higher** — [python.org/downloads](https://www.python.org/downloads/)
- **FFmpeg** — required for MP3 support (via pydub)
- **FluidSynth** — required for MIDI playback / synthesis

---

## Step-by-Step Setup

### 1. Clone / place the project

Place the `8d_studio/` folder wherever you like (e.g. `C:\apps\musik\8d_studio`).

### 2. Create a Python virtual environment

Open a terminal in the `8d_studio/` directory:

```powershell
python -m venv venv
```

### 3. Activate the virtual environment

```powershell
venv\Scripts\activate
```

Your prompt will show `(venv)` when active.

### 4. Install Python dependencies

```powershell
pip install -r requirements.txt
```

This may take several minutes on first run.

### 5. Install FFmpeg

FFmpeg is required for MP3 export/import via pydub.

**Option A — winget (recommended):**
```powershell
winget install --id=Gyan.FFmpeg -e
```

**Option B — Chocolatey:**
```powershell
choco install ffmpeg
```

**Option C — manual:**
Download from [ffmpeg.org/download](https://ffmpeg.org/download.html), extract, and add the `bin/` folder to your system `PATH`.

Verify: `ffmpeg -version`

### 6. Install FluidSynth

FluidSynth is required for MIDI synthesis.

**Option A — winget:**
```powershell
winget install FluidSynth.FluidSynth
```

**Option B — manual:**
Download from [fluidsynth.org](https://www.fluidsynth.org/), install, and add to `PATH`.

After installing, make sure `libfluidsynth.dll` is accessible (either in `PATH` or in the project root).

Verify: `fluidsynth --version`

### 7. Download HRTF and SoundFont assets

```powershell
python scripts/setup_assets.py
```

This downloads:
- **MIT KEMAR HRTF** (`.sofa`) → `data/hrtf/mit_kemar.sofa` — the 8D binaural core
- **GeneralUser GS SoundFont** (`.sf2`) → `data/soundfonts/generaluser.sf2` — all 128 GM instruments

Both files are large. Download requires internet access (one-time only).

### 8. Configure API keys (optional)

Copy `.env.example` to `.env`:

```powershell
copy .env.example .env
```

Edit `.env` to add your [Freesound API key](https://freesound.org/api/) if you want
the optional Freesound sample browser.

### 9. Launch the app

```powershell
python main.py
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `No module named 'dearpygui'` | Run `pip install -r requirements.txt` inside the venv |
| MP3 files won't load | Install FFmpeg and add to PATH |
| MIDI playback silent | Install FluidSynth and add to PATH, or place `libfluidsynth.dll` in project root |
| `data/hrtf/mit_kemar.sofa` missing | Re-run `python scripts/setup_assets.py` |
| 8D effect not working | Confirm you're using **headphones**, not speakers |
| Long path errors on Windows | Enable long path support: `reg add HKLM\SYSTEM\CurrentControlSet\Control\FileSystem /v LongPathsEnabled /t REG_DWORD /d 1 /f` |

---

## Directory Structure

```
8d_studio/
├── main.py                 # Entry point
├── requirements.txt        # Python dependencies
├── .env.example            # Config template
├── ui/                     # Dear PyGui UI code
├── engine/                 # Audio processing engine
├── data/                   # HRTF, soundfonts, samples, projects
├── scripts/                # Setup utilities
└── tests/                  # Unit tests
```
