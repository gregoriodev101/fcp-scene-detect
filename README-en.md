# SceneDetect for Final Cut Pro

Automatically detects scene cuts in a video and generates a `.fcpxml` file ready to import into **Final Cut Pro X** — no file splitting, no cloud uploads, everything runs locally on your machine.

---

## What it does

The app analyzes your video frame by frame, identifies where scene changes occur, and generates a Final Cut Pro timeline (FCPXML) with each detected scene already positioned as a separate clip. When imported into Final Cut Pro, the entire video will be sliced into the timeline, ready to edit.

The original video file is **never modified**. The FCPXML simply references the file and defines the in and out points for each scene.

---

## Requirements

- macOS
- [Python 3](https://www.python.org/downloads/)
- [Homebrew](https://brew.sh) — macOS package manager

The `install.sh` script checks for and installs everything else automatically.

---

## Installation

> You only need to do this once.

Open Terminal, navigate to the project folder and run:

```bash
chmod +x install.sh run.sh
./install.sh
```

The `chmod +x` command is required to grant execution permission to `.sh` files before running them for the first time.

`install.sh` will automatically check and install:

| What | Purpose |
|---|---|
| **python-tk** | Graphical interface (Tkinter) |
| **Homebrew** | Required to install FFmpeg |
| **FFmpeg** | Video reading and processing |
| **scenedetect[opencv]** | Frame-by-frame scene detection |
| **customtkinter** | Modern app interface |

If Homebrew is not installed, the script will display the installation command and stop. Install Homebrew, then run `./install.sh` again.

---

## How to use

### 1. Export the template from Final Cut Pro

The app needs a `.fcpxml` file exported from your Final Cut Pro project to inherit the correct frame rate, resolution, and timecode settings.

In Final Cut Pro, with a project open:
```
File → Export XML…
```

Save the file in the project folder. If the exported file is a `.fcpxmld` folder, the file you need to select is inside it with the `.fcpxml` extension.

> You only need to do this once per project. The same template can be reused for multiple videos from the same project.

### 2. Open the app

```bash
./run.sh
```

### 3. Select the files

- **Video** — the `.mov`, `.mp4`, or similar file you want to analyze
- **FCPXML Template** — the `.fcpxml` file exported from Final Cut Pro

### 4. Adjust the settings

**Sensitivity (Threshold)**
Controls how different two frames need to be for the app to consider it a scene change.
- Low values (e.g. 10–15) → detects more scenes, including subtle cuts
- High values (e.g. 40–60) → detects only hard cuts, fewer scenes
- Default: `27` — works well for most videos

**Minimum duration (s)**
Ignores scenes shorter than this value in seconds. Useful to avoid false positives in videos with flashes or fast camera movements.
- Default: `1.0s`

**Method**
- `content` — detects changes in the visual content of the frame (color, brightness, motion). Recommended for most cases.
- `threshold` — detects changes based on the average brightness of the frame only. Useful for videos with fade to black/white transitions.

### 5. Generate the FCPXML

Click **🎬 Detect Scenes and Generate FCPXML**.

The log will show the analysis progress and list each detected scene with its timecodes. When finished, the folder containing the generated file opens automatically in Finder.

### 6. Import into Final Cut Pro

```
File → Import → XML…
```

Select the `_scenes.fcpxml` file generated in the same folder as your video.

---

## Project files

```
scene-detect/
├── SceneDetect.py          ← main app (interface + logic)
├── scene_detect_fcpxml.py  ← command line version (CLI)
├── install.sh              ← automatic dependency installer
├── run.sh                  ← launches the app
├── README.md               ← documentation (Portuguese)
└── README-en.md            ← documentation (English)
```

---

## Command line version (optional)

If you prefer to use it without the graphical interface:

```bash
source venv/bin/activate
python scene_detect_fcpxml.py --video my_video.mov --template Info.fcpxml
```

Available options:

```
--video           Path to the video file (required)
--template        Path to the Final Cut Pro .fcpxml file (required)
--output          Output file name (default: <video>_scenes.fcpxml)
--threshold       Sensitivity (default: 27.0)
--min-scene       Minimum scene duration in seconds (default: 1.0)
--method          content or threshold (default: content)
--project-name    Project name in Final Cut Pro
--event-name      Event name in Final Cut Pro
```

---

## License

MIT — free to use, modify, and distribute.
