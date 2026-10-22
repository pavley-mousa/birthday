# Cinematic 20th Birthday UI

I turned 20 and didn't feel like posting the usual photo dump. So I spent a
weekend building the birthday post instead: one Python script that hijacks
your webcam, pretends to scan your face, crashes on purpose, plays your old
photos back as a beat-up camcorder tape, and lands on a full cinematic scene
with a cake and fireworks.

You run it fullscreen, hit record on your screen recorder, and that's the video.

Everything is drawn at runtime — no video editor, no After Effects, no
premade assets. Just OpenCV, Pillow and Tkinter doing more than they were
probably meant to.

---

## The 3 acts

**Act 1 — the scan, then the crash.** Fullscreen webcam with a Haar cascade
tracking your face, corner brackets, a sweep line, a progress bar, the whole
fake-biometric thing. It "identifies" you, prints `Age: 19.99`, and then the
system falls apart: RGB channels split, the frame tears into slices, red wash,
and a big `ERROR: TEENAGER LIMITS EXCEEDED` banner while a boot log types
itself out. 8 seconds of scan, ~2.6 of meltdown.

**Act 2 — the nostalgia reel.** Your 5 photos as a worn-out camcorder tape.
Sepia grade, lifted blacks, vignette, moving film grain, blinking REC, a
battery that drains, a running timecode, and the occasional tape wobble.
Crossfades between shots, then a dip to black.

**Act 3 — the celebration.** A 2:1 cinematic frame with four layers running at
once: a firework particle system bursting in the background, your photos
drifting upward as small glass panes, a big 3-tier cake with lit "20" candles
sitting in a pool of gold light, and the typography on a frosted glass panel.

---

## The parts that were actually hard

**Center-crop that doesn't behead people.** The reel fills the screen with
every photo, no black bars, whatever shape the photo is. That means scaling by
the *larger* ratio and throwing away the overflow. Cropping the overflow evenly
looks fine until you feed it portrait shots — then it takes as much off the top
as the bottom and everyone loses their forehead. I tried anchoring the crop to
the top instead and that was worse: in half my photos the subject sits
mid-frame, so a top crop framed a ceiling and a night sky beautifully. It now
runs the face detector over each photo first and places the face about 42% down
the frame. No face found (profiles, back of the head) and it just stays centred,
because guessing is how you end up with the ceiling shot.

**Glassmorphism in Tkinter, which has no alpha and no blur.** You can't do a
frosted panel with canvas widgets. What you *can* do is composite the whole
frame yourself, grab the region under the panel, blur it, lift it with a white
veil, mask it to rounded corners, and paint it back. Because it blurs the live
frame, the photo panes actually smear as they drift behind the glass. Blurring a
quarter-size copy and scaling it back up looks identical to blurring the full
region and costs about a third as much.

**Not dropping frames.** This was most of the work.

- Tk hands images to the screen at roughly 80 MP/s, so a full 1600x900 blit
  costs ~20ms before I've drawn anything. That's why Act 3 renders to a 2:1
  frame — fewer pixels, and the mattes suit it anyway.
- A *transparent* image goes to Tk about 20x slower than an opaque one
  (28ms vs 1.3ms for one cake frame). Act 3 needed ~70 of them, which froze the
  cut for 1.6s. Everything now gets flattened onto its backdrop up front.
- Film grain via `numpy` int16 round-trip: 16ms a frame. Same result through
  `cv2.add` with a saturating cast: 5ms.
- Face detection at 720p is ~82ms per call. On a 480px-wide copy it's ~21ms and
  just as accurate for a face that fills the frame.
- `after(15)` doesn't mean 15ms — Windows' timer granularity lands it near 45.
  The loop asks for whatever's left of the frame budget instead, with a 5ms
  floor, because `after(1)` spins the timer queue hard enough to starve your
  keypresses.
- All the heavy prep (photo grading, cake frames, backdrop, text) runs on a
  worker thread while Act 1 is on screen, so the transitions don't stall.

Act 1 sits at ~26fps (that's the webcam's own ceiling), Act 2 ~29, Act 3 ~28.

**The cake.** It tries to download `3d_cake.gif` on first run. Every stable
public "3D cake gif" I could actually verify turned out to be line art or 2005
clipart, so there's a cake rendered from scratch in the script instead —
shaded cylinder tiers, gold bands that follow the curve, number candles with
flames that flicker across the loop. That's the one you see by default. Drop
your own `3d_cake.gif` in the folder and it uses that instead, automatically.

---

## Running it

```bash
git clone https://github.com/er5n/birthday_upgrade.git
cd birthday_upgrade
pip install -r requirements.txt
```

Drop 5 photos next to the script named `1.jpg` through `5.jpg`. Any size, any
shape — portrait, square, a 320x240 potato from 2009, doesn't matter, they all
get cropped to fill.

```bash
python birthday_upgrade.py
```

It opens fullscreen and runs the whole thing on its own.

| key | what it does |
| --- | --- |
| `SPACE` | skip to the next act |
| `R` | restart from the top (for another take) |
| `ESC` / `Q` | quit |

Start your screen recorder *before* you launch it, or you'll miss the scan.
Close anything else using your webcam first — Zoom and Teams will hold it and
you'll get a black feed.

`haarcascade_frontalface_default.xml` is in the repo because OpenCV 5 stopped
shipping it in the wheel. Without it the scanner still runs, it just uses a
centred box instead of tracking your face.

Everything you'd want to change — timings, colours, cake size, message text,
how many fireworks — is in the config block at the top of the file.

Built and tested on Windows. The webcam backend, the beeps and the font paths
are Windows-specific, so other platforms will need small tweaks.

---

Developed by Abdullah Mahmoud ([@er5n](https://github.com/er5n))
