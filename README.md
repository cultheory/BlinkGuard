# BlinkGuard

BlinkGuard is a minimal Windows desktop app that watches for blinks through the local webcam.

If a face is detected and no blink is detected for the configured number of seconds, BlinkGuard shows a fullscreen black overlay on the primary monitor. When the user blinks again, the overlay is hidden immediately. Pressing `Esc` also hides the overlay, and pressing `Ctrl+Alt+Q` force-quits the app.

## Requirements

- Windows
- Python 3.11
- Webcam

## Run

Run [run.bat](C:\Users\siski\Documents\Codex1\run.bat).

This script creates `.venv` if needed, installs required packages, and starts the app.

## Build

Run [package.bat](C:\Users\siski\Documents\Codex1\package.bat).

After a successful build, the executable is created at [dist/BlinkGuard/BlinkGuard.exe](C:\Users\siski\Documents\Codex1\dist\BlinkGuard\BlinkGuard.exe).

## UI

- `Start`
- `Stop`
- `No blink timeout (seconds)`

## Notes

- Single monitor only
- Camera `0` only
- No tray, stats, or extra settings
- Overlay is created once and reused
