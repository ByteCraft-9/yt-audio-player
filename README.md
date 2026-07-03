# YT Audio — minimal YouTube audio player

A tiny PyQt5 desktop app that plays the **audio only** from any YouTube
video or playlist — no video is ever decoded or shown, so it's light and
doesn't distract anyone glancing at your screen.

## Setup

```bash
pip install -r requirements.txt
```

You also need the **VLC application itself** installed (not just the
Python package) — playback uses libVLC under the hood, matching your
Python's bitness (almost always 64-bit):
👉 https://www.videolan.org/vlc/

**Why VLC and not Qt's built-in player:** YouTube's audio stream links
only work if the request sends the same User-Agent/Referer header yt-dlp
used to fetch them. Qt's Windows backend (DirectShow) can't attach custom
HTTP headers, so it gets rejected by YouTube (shows up as
`DirectShowPlayerService::doRender ... 0x80040218`). libVLC accepts those
headers directly, so streams play reliably on Windows/macOS/Linux — while
still being audio-only, nothing is rendered.

> **Global hotkeys note:** the `keyboard` package needs elevated access to
> listen system-wide.
> - **Windows:** works for a normal user.
> - **Linux:** run with `sudo`, or add your user to the `input` group.
> - **macOS:** grant Accessibility permission to your terminal/app in
>   System Settings → Privacy & Security.
>
> If hotkeys can't register, the app still works fine from its own window —
> you'll just see a note in the status line.

## Run

```bash
python main.py
```

## Using it

- **Paste a YouTube video or playlist URL** into the box and hit **Go** (or
  Enter) — it loads and starts playing immediately.
- **Type a search query instead** and hit **Go** — a small results list
  pops up showing only **title + channel** (no thumbnails). Double-click
  one to play it.
- Playlists queue up automatically; **⏭ / ⏮** move between tracks, and it
  auto-advances when a track ends.

## Controls

| Control            | In-window        | Global hotkey       |
|---------------------|-------------------|----------------------|
| Play / Pause        | ▶ / ⏸ button      | `Ctrl+Alt+P`         |
| Skip forward 3s     | 3⏩ button        | `Ctrl+Alt+→`         |
| Skip backward 3s    | ⏪3 button        | `Ctrl+Alt+←`         |
| Next track           | ⏭ button          | `Ctrl+Alt+N`         |
| Previous track       | ⏮ button          | `Ctrl+Alt+B`         |
| Seek to position      | drag the slider   | —                    |
| Volume                | slider            | —                    |
| Playback speed         | 0.5x–2x dropdown | —                    |

## Behavior

 - Closing the window **quits the application** (no longer minimizes to
   the tray). Audio stops and the app exits when you close the window.
- The window is fixed-size (340×232px) and shows only the controls — no
  extra chrome.

## Project layout

```
yt_audio_player/
├── main.py                # entry point
├── core/
│   ├── yt_service.py       # yt-dlp: resolve stream / playlist / search
│   ├── audio_engine.py     # QMediaPlayer wrapper (playback, queue, speed)
│   ├── workers.py          # background QThread for blocking yt-dlp calls
│   └── hotkeys.py          # global hotkey registration
└── ui/
    ├── main_window.py      # the compact main window
    └── search_dialog.py    # title+channel search results popup
```

## Known limitations

- YouTube stream URLs are time-limited; if you leave a paused track idle
  for a long time, resuming may need a fresh resolve (rare in normal use).
- Age-restricted or region-locked videos may fail to resolve — yt-dlp will
  raise an error, shown as a small popup.

## Build a Windows executable (.exe)

You can bundle this app into a single Windows `.exe` using PyInstaller. A
couple of notes:

- Install PyInstaller: `pip install pyinstaller`.
- If you want the bundled executable to run without a separate VLC
  installation on the target machine, you must include VLC's `libvlc`/
  `libvlccore` and the `plugins` folder. Paths below assume a standard
  VLC install on Windows — adjust them to your system.

Example commands:
D:\VLC
```bash
pyinstaller --noconfirm --onefile --windowed `
  --add-binary "D:\VLC\libvlc.dll;." `
  --add-binary "D:\VLC\libvlccore.dll;." `
  --add-data "D:\VLC\plugins;plugins" `
  main.py
```

After the build, the single-file executable will be in the `dist/`
folder. If you omitted the VLC binaries, ensure the target machine has a
matching VLC installed (same bitness) so `python-vlc` can find libVLC.
