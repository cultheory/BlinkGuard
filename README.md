# BlinkGuard

BlinkGuard is a minimal Windows desktop app that watches for blinks through the local webcam.

It is designed to help protect your vision by preventing your eyes from becoming dry when you stay too focused and forget to blink. 

If a face is detected and no blink is detected for the configured number of seconds, BlinkGuard shows a fullscreen black overlay on the primary monitor. 
When the user blinks again, the overlay is hidden immediately. 
Pressing `Esc` also hides the overlay, and pressing `Ctrl+Alt+Q` force-quits the app.

## Requirements

- Windows
- Python 3.11
- Webcam

## Run

To run the app, execute `run.bat`.

This script creates a `.venv` virtual environment if needed, installs the required packages, and launches the app.

## Build

To build the app, execute `package.bat`.

After a successful build, the executable will be available at `dist/BlinkGuard/BlinkGuard.exe`.

## UI

- `Start`
- `Stop`
- `No blink timeout (seconds)`

## Notes
Currently,
- Single monitor only
- Supports only the default webcam (camera 0)
- No tray, stats, or extra settings
- Overlay is created once and reused
