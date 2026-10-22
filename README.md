# Pavley's 20th Birthday Animation

A fullscreen Python animation in three acts: a biometric-style scan, a nostalgic photo reel, and a birthday celebration with a cake, fireworks, floating memories, and a birthday message.

## Run it on Windows

Install the dependencies:

```powershell
py -3.14 -m pip install -r requirements.txt
```

Then start the animation:

```powershell
py -3.14 birthday_upgrade.py
```

The app opens fullscreen by default.

## Files

- `birthday_upgrade.py` — safe launcher with Pavley's settings and an OpenCV compatibility fallback.
- `birthday_upgrade_original.py` — the original full animation implementation, preserved unchanged.
- `1.jpg` through `15.jpg` — photos shown in numerical order during the main slideshow.
- `3d_cake.gif` — optional custom cake animation; the program has a built-in cake fallback.
- `haarcascade_frontalface_default.xml` — optional face detector data.

The slideshow preserves the full photo over a blurred background, rather than cropping the main photo to fill the screen. Small decorative memory panes in the celebration may be square-cropped intentionally.

## OpenCV compatibility

Some OpenCV builds do not expose `cv2.CascadeClassifier`. The launcher detects that situation and continues with a centered scan box rather than crashing. Face tracking is optional; the slideshow and celebration still run.

## Controls

| Key | Action |
| --- | --- |
| `SPACE` | Skip to the next act |
| `R` | Restart the sequence |
| `ESC` or `Q` | Quit |

Settings such as the display name, handle, age shown in the scanner, photo order, fullscreen mode, and birthday message are set in `birthday_upgrade.py`.
