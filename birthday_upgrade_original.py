"""
SYSTEM UPGRADE 19 -> 20   |   Pavley Mousa (@er5n)
=======================================================
A three-act screen-recording piece:

  ACT 1  Scanner + glitch  - face detection, "Identified", then the system
                             falls apart: RGB split, red wash, ERROR banner
  ACT 2  Nostalgia reel    - 1.jpg..5.jpg as a vintage camcorder slideshow
  ACT 3  Celebration       - fireworks, drifting memories, a massive
                             cake, and the message on frosted glass

HOTKEYS (handy while filming):
  SPACE  skip ahead one act (scan -> reel -> celebration)
  R      restart the whole sequence (for another take)
  ESC/Q  quit

ASSETS - the script is self-sufficient; nothing has to be found by hand:
  3d_cake.gif      downloaded automatically on first run (see ensure_cake).
                   Drop your own in and it is used instead. With no file and
                   no network, a 3D cake is rendered from scratch.
  1.jpg .. 5.jpg   the reel. Any size or aspect ratio; each is fitted to the
                   screen with black bars, never stretched.

Requires: opencv-python, customtkinter, pillow, numpy, requests

Run:  python birthday_upgrade.py
"""

import math
import os
import random
import threading
import time
import tkinter as tk

import cv2
import numpy as np
import customtkinter as ctk
from PIL import (Image, ImageChops, ImageDraw, ImageFilter, ImageFont,
                 ImageSequence, ImageTk)

# --------------------------------------------------------------------------
# CONFIG - tweak anything here
# --------------------------------------------------------------------------
SCAN_NAME = "Pavley Mousa"
SCAN_AGE = "19.99"
PARTY_NAME = "Pavley Mousa"
PARTY_TAG = "@eng.bevo"
ERROR_TITLE = "ERROR: TEENAGER LIMITS EXCEEDED"

MESSAGE = (
    "Today, I unlock a new chapter of my life. Grateful for everyone who "
    "walked by my side this past year. I leave behind the sweet and the "
    "bitter, stepping into this new era with hope and optimism. May this "
    "year bring blessings and turn my greatest dreams into reality."
)

SLIDE_FILES = ["1.jpg", "2.jpg", "3.jpg", "4.jpg", "5.jpg","6.jpg","7.jpg","8.jpg", "9.jpg", "10.jpg", "11.jpg", "12.jpg","13.jpg","14.jpg","15.jpg"]
CAKE_GIF = "3d_cake.gif"

# Verified direct links (each was fetched and checked: real GIF, animated,
# transparent background). First one wins; the rest are fallbacks.
CAKE_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/d/d4/WP25_Birthday_cake.gif",
    "https://i.gifer.com/3TsW.gif",
    "https://i.gifer.com/32qR.gif",
]
# A cake you supply yourself is always used. This flag only decides what to
# do with the auto-downloaded one: the public GIFs that could be verified as
# stable + transparent are line-art/clipart rather than rendered 3D, and the
# built-in render matches the gold palette far better. Flip to True to use
# the downloaded file instead.
PREFER_DOWNLOADED_CAKE = False

SCAN_SECONDS = 8.0      # act 1, scanning
GLITCH_SECONDS = 2.6    # act 1, the meltdown
SLIDE_SECONDS = 3.2     # act 2, per photo (includes its crossfade)
FADE_SECONDS = 0.9      # crossfade length
IDENTIFY_AT = 2.2       # when "Scanning..." flips to "Identified"

CAM_INDEX = 0
FULLSCREEN = True
MAX_VIDEO_H = 2400       # cap webcam display height (keeps playback smooth)
DETECT_W = 480.0        # face detection runs on a frame this wide (speed)
REEL_MAX_W = 1920       # cap reel resolution; full 4K frames would stall Tk
# Act 2 cropping. A detected face is placed FACE_FOCUS down the frame, which
# is what actually stops heads being cut off. PORTRAIT_ANCHOR is only the
# fallback for photos with no detectable face (profiles, backs of heads):
# 0.5 keeps them centred, which is right when the subject is mid-frame.
# Lower it toward 0.2 to bias undetected shots upward.
FACE_FOCUS = 0.42
PORTRAIT_ANCHOR = 0.5
# Frame budget. Windows' Tk timer granularity is ~15ms, so asking for 33ms
# actually lands near 45ms (~22fps). 16 gives ~30fps on the camera (the
# webcam's own ceiling). Measured, not guessed.
FRAME_MS = 16
CAKE_SCALE = 1.55       # act 3 centrepiece, relative to the old size
MEMORY_SQUARES = 9      # drifting photo panes in act 3
FIREWORK_DIV = 4        # fireworks render at 1/N resolution, then bloom
# Act 3 is composited in software and handed to Tk as one image per frame.
# That blit runs at ~80 MP/s, so it alone costs 20ms at a full 1600x900.
# Rendering to a 2:1 cinematic frame instead drops it to ~17ms and buys the
# ~30fps the recording needs - and the slim mattes suit the piece.
ACT3_ASPECT = 16 / 9

# ---- act 3 palette: deep space blue + gold ------------------------------
SPACE = "#04091A"
SPACE2 = "#0D1A3C"
GOLD = "#F3C969"
GOLD_HI = "#FFEFC9"
GOLD_LO = "#A9761F"
MIST = "#9DB2DE"
TEXT_HI = "#EEF3FF"

GREEN = (120, 255, 0)   # BGR, act 1 HUD
WHITE = (255, 255, 255)
RED = (60, 60, 255)
CYAN = (255, 220, 0)

BOOT_LINES = [
    "> RUNNING age_validation.exe ............ FAIL",
    "> teenager.sys .......................... CORRUPT",
    "> memory of being 19 .................... ARCHIVED",
    "> patching USER: 19 -> 20 ...............",
    "> REBOOT REQUIRED. LOADING memories.tape",
]


def here(*parts):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


# --------------------------------------------------------------------------
# Asset setup - runs at startup
# --------------------------------------------------------------------------
def ensure_cake(timeout=8):
    """Make sure 3d_cake.gif exists, downloading it if it does not.

    Never fatal: the celebration falls back to a cake rendered in-process, so
    a missing file, no network, or a dead link all still give a finished show.
    """
    path = here(CAKE_GIF)
    marker = path + ".auto"
    if os.path.exists(path) and os.path.getsize(path) > 2048:
        # A marker recorded at download time says this file came from the
        # fallback list rather than from you. The size is stored too, so
        # replacing the GIF with your own is detected even if the marker
        # is left behind.
        auto = False
        try:
            with open(marker) as fh:
                auto = int(fh.readline().strip()) == os.path.getsize(path)
        except Exception:
            auto = False
        print("[+] %s already present (%s)"
              % (CAKE_GIF, "auto-downloaded" if auto else "your own file"))
        return path, auto
    try:
        import requests
    except ImportError:
        print("[i] requests not installed - using the built-in 3D cake.")
        return None, False

    headers = {"User-Agent": "Mozilla/5.0 (BirthdayUpgrade/1.0)"}
    for url in CAKE_URLS:
        try:
            print("[.] fetching %s" % url)
            r = requests.get(url, timeout=timeout, headers=headers)
            r.raise_for_status()
            if not r.content.startswith(b"GIF8"):
                print("[!] not a GIF, skipping")
                continue
            tmp = path + ".part"
            with open(tmp, "wb") as fh:
                fh.write(r.content)
            with Image.open(tmp) as probe:      # refuse a truncated download
                probe.verify()
            os.replace(tmp, path)               # atomic: no half-written file
            with open(marker, "w") as fh:      # remember where it came from
                fh.write("%d\n%s\n" % (os.path.getsize(path), url))
            print("[+] saved %s (%d KB)" % (CAKE_GIF, len(r.content) // 1024))
            return path, True
        except Exception as e:
            print("[!] %s failed (%s)" % (url.split("/")[-1], e))
            try:
                os.remove(path + ".part")
            except OSError:
                pass
    print("[i] Could not download a cake - using the built-in 3D render.")
    return None, False


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def load_cascade(quiet=False):
    """Find haarcascade_frontalface_default.xml.

    OpenCV 5 wheels no longer ship the cascade XML, so look in a few places:
    next to this script, in cv2's data dir, and in any local venv.
    """
    name = "haarcascade_frontalface_default.xml"
    candidates = [here(name)]
    try:
        candidates.append(os.path.join(cv2.data.haarcascades, name))
    except Exception:
        pass
    for venv in ("venv", ".venv", "env"):
        candidates.append(here(venv, "Lib", "site-packages", "cv2", "data", name))
    for path in candidates:
        if os.path.exists(path):
            c = cv2.CascadeClassifier(path)
            if not c.empty():
                if not quiet:
                    print("[+] Face cascade: %s" % path)
                return c
    print("[!] No face cascade found - the HUD will use a centred target box.")
    return None


def pick_ttf(names):
    """Find a TTF file by filename (PIL needs a path, not a family name)."""
    root = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for n in names:
        p = os.path.join(root, n)
        if os.path.exists(p):
            return p
    return None


def fit_ttf_size(path, text, max_w, start):
    """Largest size at which the text still fits the given width."""
    size = start
    while size > 12:
        if ImageFont.truetype(path, size).getlength(text) <= max_w:
            break
        size -= 2
    return max(12, size)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in rgb)


def mix(c1, c2, t):
    """Blend two hex colours (t=0 -> c1, t=1 -> c2)."""
    a, b = hex_to_rgb(c1), hex_to_rgb(c2)
    return rgb_to_hex([a[i] + (b[i] - a[i]) * t for i in range(3)])


def put(img, text, org, scale, color, thick=2, font=cv2.FONT_HERSHEY_DUPLEX):
    """Text with a dark outline so it stays readable over any footage."""
    cv2.putText(img, text, org, font, scale, (0, 0, 0), thick + 3, cv2.LINE_AA)
    cv2.putText(img, text, org, font, scale, color, thick, cv2.LINE_AA)


def corner_box(img, x, y, w, h, color, thick=3, frac=0.22):
    """Sci-fi corner brackets instead of a boring full rectangle."""
    cx, cy = int(w * frac), int(h * frac)
    pts = [((x, y), (x + cx, y), (x, y + cy)),
           ((x + w, y), (x + w - cx, y), (x + w, y + cy)),
           ((x, y + h), (x + cx, y + h), (x, y + h - cy)),
           ((x + w, y + h), (x + w - cx, y + h), (x + w, y + h - cy))]
    for p0, p1, p2 in pts:
        cv2.line(img, p0, p1, color, thick, cv2.LINE_AA)
        cv2.line(img, p0, p2, color, thick, cv2.LINE_AA)


def wrap_text(text, font, max_w):
    """Greedy word wrap against real glyph widths."""
    words, lines, cur = text.split(), [], []
    for w in words:
        trial = cur + [w]
        if cur and font.getlength(" ".join(trial)) > max_w:
            lines.append(" ".join(cur))
            cur = [w]
        else:
            cur = trial
    if cur:
        lines.append(" ".join(cur))
    return lines


def paragraph_image(text, ttf, size, max_w, color, line_spacing=1.62,
                    shadow=True):
    """A centred block of copy with generous leading and a soft drop shadow."""
    font = ImageFont.truetype(ttf, size)
    lines = wrap_text(text, font, max_w)
    lh = int(size * line_spacing)
    pad = int(size * 2.1)
    w = int(max(font.getlength(l) for l in lines)) + pad * 2
    h = lh * len(lines) + pad * 2
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    for i, line in enumerate(lines):
        lw = font.getlength(line)
        d.text(((w - lw) / 2, pad + i * lh), line, font=font, fill=255)

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sh.putalpha(mask.filter(ImageFilter.GaussianBlur(size * 0.30)).point(
            lambda v: int(v * 0.85)))
        out = Image.alpha_composite(out, ImageChops.offset(sh, 0, int(size * 0.16)))
    body = Image.new("RGBA", (w, h), hex_to_rgb(color) + (0,))
    body.putalpha(mask)
    return Image.alpha_composite(out, body), len(lines)


# --------------------------------------------------------------------------
# ACT 1 - the glitch
# --------------------------------------------------------------------------
def draw_glitch(img, gt, total):
    """gt = seconds into the meltdown."""
    h, w = img.shape[:2]
    inten = min(1.0, 0.35 + gt / total)

    dx = random.randint(-int(28 * inten), int(28 * inten)) or 6
    b, g, r = cv2.split(img)
    img = cv2.merge([np.roll(b, dx, 1), g, np.roll(r, -dx, 1)])

    for _ in range(int(10 * inten) + 2):            # torn slices
        yy = random.randint(0, max(1, h - 6))
        hh = random.randint(6, 46)
        img[yy:yy + hh] = np.roll(img[yy:yy + hh], random.randint(-90, 90), axis=1)

    for _ in range(int(6 * inten)):                 # dead blocks
        bx = random.randint(0, max(1, w - 60))
        by2 = random.randint(0, max(1, h - 30))
        bw2, bh2 = random.randint(30, 140), random.randint(8, 26)
        img[by2:by2 + bh2, bx:bx + bw2] = random.choice(
            [(255, 255, 255), (0, 0, 255), (255, 0, 128), (0, 0, 0)])

    img[::3] = (img[::3] * 0.5).astype(np.uint8)    # scanlines
    if random.random() < 0.12:
        img = cv2.applyColorMap(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY),
                                cv2.COLORMAP_HOT)

    wash = np.zeros_like(img)
    wash[:] = (0, 0, 200)                           # red alert
    img = cv2.addWeighted(img, 1 - 0.18 * inten, wash, 0.18 * inten, 0)
    if random.random() < 0.10:
        img = 255 - img

    jx, jy = random.randint(-7, 7), random.randint(-5, 5)
    by = h // 2 - 60
    cv2.rectangle(img, (0, by + jy), (w, by + 78 + jy), (0, 0, 0), -1)
    cv2.rectangle(img, (0, by + jy), (w, by + 78 + jy), RED, 3)
    put(img, ERROR_TITLE, (34 + jx, by + 54 + jy), 1.35 if w > 900 else 0.9, RED, 3)
    put(img, "Error code: 0x00000020   //   AGE OVERFLOW",
        (36, by + 112), 0.7, WHITE, 1)

    shown = int((gt / total) * (len(BOOT_LINES) + 0.5))
    for i, line in enumerate(BOOT_LINES[:max(0, shown)]):
        put(img, line, (34, by + 158 + i * 30), 0.62,
            CYAN if i == len(BOOT_LINES) - 1 else GREEN, 1,
            cv2.FONT_HERSHEY_SIMPLEX)
    return img


# --------------------------------------------------------------------------
# ACT 2 - vintage reel
# --------------------------------------------------------------------------
def face_focus(img, cascade):
    """Where the faces sit vertically, as a fraction of the image height.

    Returns None when nothing is found, which is common and fine - profiles
    and turned heads are invisible to a frontal cascade.
    """
    if cascade is None:
        return None
    h, w = img.shape[:2]
    s = 640.0 / float(w)
    small = cv2.resize(img, (640, max(1, int(h * s))), interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
    try:
        found = cascade.detectMultiScale(gray, 1.15, 5, minSize=(30, 30))
    except cv2.error:
        return None
    if len(found) == 0:
        return None
    sh = float(small.shape[0])
    area = sum(float(fw * fh) for _, _, fw, fh in found)      # biggest face wins
    return sum((y + fh / 2.0) * fw * fh for _, y, fw, fh in found) / (area * sh)


def cover(img, W, H, focus=None, anchor=PORTRAIT_ANCHOR):
    """Crop-and-fill that keeps heads in frame.

    Scales by the LARGER of the two ratios so no bar is ever left, then trims
    the overflow. Width is taken evenly from both sides. Height is not: a
    portrait dropped into a landscape frame has a lot of vertical excess, and
    splitting it evenly cuts as much off the top as the bottom - exactly
    where the faces are.

    `focus` is the vertical position of the subject (0..1 of the source
    height, from face_focus). When given, the crop is placed so the subject
    lands FACE_FOCUS down the frame. Without it the crop keeps `anchor` of
    the excess above - a bias toward the top, not a hard top crop, since a
    hard one frames the sky whenever the subject is centred.

    Landscape sources are unaffected: their vertical excess is zero.
    """
    h, w = img.shape[:2]
    s = max(W / float(w), H / float(h))
    nw, nh = max(W, int(math.ceil(w * s))), max(H, int(math.ceil(h * s)))
    interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
    big = cv2.resize(img, (nw, nh), interpolation=interp)
    x = (nw - W) // 2                                  # width: still centred
    excess = nh - H
    if excess <= 0:
        y = 0
    elif focus is not None:
        y = int(round(focus * nh - H * FACE_FOCUS))    # sit the face in frame
        y = max(0, min(excess, y))
    else:
        y = int(round(excess * min(max(anchor, 0.0), 1.0)))
    return big[y:y + H, x:x + W]


def fit_photo(img, W, H, focus=None):
    """Show the complete photo over a blurred, full-screen background."""
    h, w = img.shape[:2]

    # Blurred background fills the whole screen.
    background = cover(img, W, H, focus=focus)
    sigma = max(8, int(min(W, H) * 0.025))
    background = cv2.GaussianBlur(
        background, (0, 0), sigmaX=sigma, sigmaY=sigma
    )
    background = cv2.convertScaleAbs(background, alpha=0.42)

    # Foreground preserves the entire original photo.
    scale = min(W / float(w), H / float(h))
    new_w = max(1, min(W, int(round(w * scale))))
    new_h = max(1, min(H, int(round(h * scale))))

    interpolation = (
        cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    )
    foreground = cv2.resize(
        img, (new_w, new_h), interpolation=interpolation
    )

    x = (W - new_w) // 2
    y = (H - new_h) // 2
    background[y:y + new_h, x:x + new_w] = foreground

    return background

def build_vignette(W, H, strength=0.72):
    kx = cv2.getGaussianKernel(W, W * 0.52)
    ky = cv2.getGaussianKernel(H, H * 0.52)
    mask = ky @ kx.T
    mask = mask / mask.max()
    return ((1.0 - strength) + strength * mask).astype(np.float32)[:, :, None]


def vintage(img, vig):
    """Sepia grade + faded blacks + vignette. Applied once per photo."""
    sepia = np.array([[0.272, 0.534, 0.131],
                      [0.349, 0.686, 0.168],
                      [0.393, 0.769, 0.189]])
    out = np.clip(cv2.transform(img, sepia), 0, 255).astype(np.uint8)
    out = cv2.addWeighted(img, 0.28, out, 0.72, 0)       # keep a little life
    out = cv2.convertScaleAbs(out, alpha=0.92, beta=16)  # lifted, faded blacks
    return (out.astype(np.float32) * vig).astype(np.uint8)


def grain_bank(W, H, n=6, amount=13):
    """A few pre-made grain fields, cycled per frame.

    Generating noise every frame costs more than the whole rest of the
    composite, and cycling a handful is indistinguishable on camera.
    """
    return [np.repeat(np.random.normal(0, amount, (H, W, 1)).astype(np.int16),
                      3, axis=2) for _ in range(n)]


def draw_camcorder(frame, t, idx, total):
    """Retro camcorder furniture: REC, battery, timecode, tape wobble."""
    h, w = frame.shape[:2]
    m = int(min(w, h) * 0.045)
    fs = min(w, h) / 900.0

    if (t % 1.4) < 0.85:
        cv2.circle(frame, (m + 12, m + 6), int(11 * fs) + 3, (60, 60, 235), -1,
                   cv2.LINE_AA)
        put(frame, "REC", (m + 34, m + 15), 0.85 * fs, (245, 245, 245), 2)

    bw, bh = int(58 * fs), int(26 * fs)
    bx, by = w - m - bw, m - 6
    cv2.rectangle(frame, (bx, by), (bx + bw, by + bh), (235, 235, 235), 2)
    cv2.rectangle(frame, (bx + bw + 2, by + bh // 3),
                  (bx + bw + 8, by + 2 * bh // 3), (235, 235, 235), -1)
    for i in range(3 if (t % 6) < 4 else 2):
        cv2.rectangle(frame, (bx + 4 + i * (bw - 6) // 3, by + 4),
                      (bx + (i + 1) * (bw - 6) // 3, by + bh - 4),
                      (235, 235, 235), -1)

    total_s = int(t)
    tc = "%02d:%02d:%02d:%02d" % (0, total_s // 60, total_s % 60,
                                  int((t % 1) * 25))
    put(frame, tc, (w - m - int(210 * fs), h - m), 0.75 * fs, (235, 235, 235), 2)
    put(frame, "PLAY  >", (m, h - m - int(34 * fs)), 0.7 * fs, (235, 235, 235), 2)
    put(frame, "MEMORY  %02d / %02d" % (idx + 1, total), (m, h - m),
        0.7 * fs, (235, 235, 235), 2)
    corner_box(frame, m - 8, m - 18, w - 2 * m + 16, h - 2 * m + 36,
               (215, 215, 215), 2, frac=0.05)

    if random.random() < 0.05:
        y = random.randint(0, max(1, h - 3))
        band = frame[y:y + random.randint(2, 5)]
        frame[y:y + band.shape[0]] = np.roll(band, random.randint(-14, 14), 1)
    return frame


# --------------------------------------------------------------------------
# ACT 3 - artwork
# --------------------------------------------------------------------------
def build_backdrop(W, H):
    """Deep space blue: gradient, a warm core glow, drifting bokeh, stars."""
    top, bottom = np.array(hex_to_rgb(SPACE2)), np.array(hex_to_rgb(SPACE))
    ramp = np.linspace(0, 1, H)[:, None] ** 0.7
    img = np.repeat((top * (1 - ramp) + bottom * ramp).astype(np.uint8)[:, None, :],
                    W, axis=1)
    bg = Image.fromarray(img, "RGB").convert("RGBA")

    # warm core behind where the cake will stand
    core = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(core).ellipse(
        [W * 0.22, H * 0.02, W * 0.78, H * 0.72],
        fill=hex_to_rgb(GOLD) + (34,))
    bg = Image.alpha_composite(bg, core.filter(
        ImageFilter.GaussianBlur(int(H * 0.10))))

    rnd = random.Random(11)
    bokeh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(bokeh)
    for _ in range(22):
        r = rnd.randint(int(H * 0.02), int(H * 0.09))
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        col = hex_to_rgb(GOLD if rnd.random() < 0.65 else MIST)
        d.ellipse([x - r, y - r, x + r, y + r], fill=col + (rnd.randint(8, 20),))
    bg = Image.alpha_composite(bg, bokeh.filter(
        ImageFilter.GaussianBlur(int(H * 0.016))))

    stars = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ds = ImageDraw.Draw(stars)
    for _ in range(150):
        x, y = rnd.randint(0, W), rnd.randint(0, H)
        r = rnd.choice([1, 1, 1, 2])
        a = rnd.randint(30, 130)
        ds.ellipse([x - r, y - r, x + r, y + r], fill=(230, 240, 255, a))
    bg = Image.alpha_composite(bg, stars)

    vig = build_vignette(W, H, 0.5)
    return Image.fromarray((np.array(bg.convert("RGB")) * vig).astype(np.uint8))


def alpha_scale(img, f):
    """A copy of an RGBA image at a fraction of its opacity."""
    if f >= 1.0:
        return img
    out = img.copy()
    out.putalpha(img.getchannel("A").point(lambda v: int(v * f)))
    return out


def build_memory_panes(files, size):
    """The photos as small square glass panes: cropped, bordered, dimmed.

    Squared with the same center-crop rule as the reel, so nothing is
    stretched, then held back in opacity so they read as distant.
    """
    panes = []
    for name in files:
        path = here(name)
        img = cv2.imread(path, cv2.IMREAD_COLOR) if os.path.exists(path) else None
        if img is None:
            continue
        sq = cover(img, size, size)
        pil = Image.fromarray(cv2.cvtColor(sq, cv2.COLOR_BGR2RGB))
        pil = pil.filter(ImageFilter.GaussianBlur(0.5))          # sit back a bit
        pane = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, size - 1, size - 1], int(size * 0.06), fill=255)
        pane.paste(pil, (0, 0), mask)
        d = ImageDraw.Draw(pane)
        d.rounded_rectangle([0, 0, size - 1, size - 1], int(size * 0.06),
                            outline=(255, 246, 226, 150), width=2)
        d.rounded_rectangle([3, 3, size - 4, size - 4], int(size * 0.05),
                            outline=(255, 255, 255, 40), width=1)
        a = pane.getchannel("A").point(lambda v: int(v * 0.34))   # distant
        pane.putalpha(a)
        panes.append(pane)
    if not panes:                       # no photos: plain glass panes
        for _ in range(3):
            pane = Image.new("RGBA", (size, size), (255, 255, 255, 16))
            ImageDraw.Draw(pane).rounded_rectangle(
                [0, 0, size - 1, size - 1], int(size * 0.06),
                outline=(255, 246, 226, 60), width=2)
            panes.append(pane)
    return panes


def glow_image(size, color, alpha=150, blur_frac=0.22):
    """A soft radial glow (used behind the cake)."""
    w, h = size
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([w * 0.16, h * 0.16, w * 0.84, h * 0.84],
                                fill=hex_to_rgb(color) + (alpha,))
    return img.filter(ImageFilter.GaussianBlur(int(min(w, h) * blur_frac)))


def text_image(text, ttf, size, fill_top, fill_bottom, glow_color=None,
               glow_strength=0.6, track=0):
    """Text with a vertical gradient fill, a soft bloom, and optional tracking."""
    font = ImageFont.truetype(ttf, size)
    if track:                                    # letterspacing for the handle
        text = (" " * track).join(list(text))
    box = ImageDraw.Draw(Image.new("L", (8, 8))).textbbox((0, 0), text, font=font)
    pad = max(16, int(size * 0.6))
    w, h = box[2] - box[0] + pad * 2, box[3] - box[1] + pad * 2
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).text((pad - box[0], pad - box[1]), text,
                              font=font, fill=255)

    top, bot = np.array(hex_to_rgb(fill_top)), np.array(hex_to_rgb(fill_bottom))
    ramp = np.linspace(0, 1, h)[:, None] ** 0.9
    grad = Image.fromarray(np.repeat(
        (top * (1 - ramp) + bot * ramp).astype(np.uint8)[:, None, :], w, axis=1), "RGB")

    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if glow_color:
        for radius, mul in ((size * 0.30, 0.55), (size * 0.10, 0.45)):
            g = Image.new("RGBA", (w, h), hex_to_rgb(glow_color) + (0,))
            g.putalpha(mask.filter(ImageFilter.GaussianBlur(radius)).point(
                lambda v, m=mul: int(v * m * glow_strength)))
            out = Image.alpha_composite(out, g)
    sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(max(2, size * 0.05))).point(
        lambda v: int(v * 0.55)))
    out = Image.alpha_composite(out, ImageChops.offset(sh, 0, max(2, size // 20)))
    body = grad.convert("RGBA")
    body.putalpha(mask)
    return Image.alpha_composite(out, body)


def render_3d_cake(height=460, frames=14):
    """A shaded, volumetric cake animation - the offline centrepiece.

    Drawn at 3x and downsampled, with a horizontal light ramp multiplied over
    the whole silhouette so the tiers read as cylinders rather than flat bars.
    """
    # 2x supersample, downsampled with LANCZOS: at the enlarged act 3 size a
    # 3x buffer cost 5s of the prep budget for no visible gain.
    S = 2
    W, H = int(height * 1.15), height
    bw, bh = W * S, H * S
    icing = [(255, 246, 236), (247, 232, 214), (240, 220, 198)]
    gold, gold_d = hex_to_rgb(GOLD), hex_to_rgb(GOLD_LO)
    out = []

    for fi in range(frames):
        ph = fi / float(frames) * 2 * math.pi
        img = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        cx = bw // 2

        # plate
        d.ellipse([cx - bw * 0.44, bh * 0.855, cx + bw * 0.44, bh * 0.945],
                  fill=(206, 214, 238, 255))
        d.ellipse([cx - bw * 0.40, bh * 0.848, cx + bw * 0.40, bh * 0.925],
                  fill=(232, 238, 255, 255))

        # three cylindrical tiers, bottom first
        tiers = [(0.375, 0.150, 0.700, 0.052),
                 (0.290, 0.140, 0.556, 0.042),
                 (0.205, 0.128, 0.420, 0.032)]
        for i, (hw, th, ty, rh) in enumerate(tiers):
            x0, x1 = cx - bw * hw, cx + bw * hw
            y0, y1 = bh * ty, bh * (ty + th)
            ry = bh * rh
            d.rectangle([x0, y0, x1, y1], fill=icing[1])
            d.ellipse([x0, y1 - ry, x1, y1 + ry], fill=icing[2])   # front curve

            # Gold band wrapping the cylinder: fill the lower ellipse, then
            # cover its top with the body colour. What is left is a crescent
            # that follows the tier's curvature - a band, not a gold pool.
            band_y = y0 + ry * 2.6
            band_h = bh * 0.016
            d.ellipse([x0, band_y + band_h - ry, x1, band_y + band_h + ry],
                      fill=gold)
            d.ellipse([x0, band_y - ry, x1, band_y + ry], fill=icing[1])
            d.arc([x0, band_y + band_h - ry, x1, band_y + band_h + ry],
                  0, 180, fill=gold_d, width=max(1, int(2 * S)))

            d.ellipse([x0, y0 - ry, x1, y0 + ry], fill=icing[0])   # top face
            # icing dripping over the rim, after the top face so it reads
            n = max(6, int(hw * 34))
            for k in range(n):
                dx = x0 + (x1 - x0) * (k + 0.5) / n
                edge = math.sqrt(max(0.0, 1 - ((dx - (x0 + x1) / 2) /
                                               ((x1 - x0) / 2)) ** 2))
                drop = bh * (0.010 + 0.018 * abs(math.sin(k * 1.7 + i)))
                d.rounded_rectangle([dx - (x1 - x0) / n * 0.42, y0 + ry * edge - 2,
                                     dx + (x1 - x0) / n * 0.42,
                                     y0 + ry * edge + drop],
                                    radius=int((x1 - x0) / n * 0.42), fill=icing[0])

        # "20" candles
        ttf = pick_ttf(["seguibl.ttf", "ariblk.ttf", "arialbd.ttf"])
        top_y = bh * 0.420
        dh = bh * 0.150
        if ttf:
            f = ImageFont.truetype(ttf, int(dh))
            for digit, off in (("2", -0.072), ("0", 0.072)):
                bbx = d.textbbox((0, 0), digit, font=f)
                x = cx + bw * off - (bbx[2] - bbx[0]) / 2 - bbx[0]
                d.text((x, top_y - dh * 0.86 - bbx[1]), digit, font=f,
                       fill=gold, stroke_width=int(2 * S), stroke_fill=gold_d)

        # flames flicker per frame
        for j, off in enumerate((-0.072, 0.072)):
            x = cx + bw * off
            flick = math.sin(ph * 2 + j * 2.1)
            fy = top_y - dh * 0.86 - bh * 0.012
            fw = bw * 0.017 * (1 + 0.14 * flick)
            fh = bh * 0.052 * (1 + 0.18 * flick)
            d.line([(x, fy + bh * 0.016), (x, fy)], fill=(70, 62, 54, 255),
                   width=int(3 * S))
            d.polygon([(x, fy - fh), (x + fw, fy - fh * 0.28),
                       (x, fy + bh * 0.004), (x - fw, fy - fh * 0.28)],
                      fill=(255, 186, 74, 255))
            d.polygon([(x, fy - fh * 0.58), (x + fw * 0.45, fy - fh * 0.16),
                       (x, fy + bh * 0.002), (x - fw * 0.45, fy - fh * 0.16)],
                      fill=(255, 248, 216, 255))

        # volumetric shading: a light ramp across the silhouette
        alpha = img.getchannel("A")
        ramp = np.linspace(0, 1, bw)
        shade = (0.62 + 0.55 * np.exp(-((ramp - 0.36) ** 2) / 0.10)).clip(0, 1.25)
        shade = np.repeat(shade[None, :, None], bh, axis=0)
        body = (np.array(img.convert("RGB")).astype(np.float32) * shade)
        img = Image.fromarray(np.clip(body, 0, 255).astype(np.uint8)).convert("RGBA")
        img.putalpha(alpha)

        # candle bloom on top
        bloom = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        db = ImageDraw.Draw(bloom)
        for off in (-0.072, 0.072):
            x = cx + bw * off
            r = bh * 0.075 * (1 + 0.12 * math.sin(ph * 2))
            db.ellipse([x - r, top_y - dh - r * 0.6, x + r, top_y - dh + r * 1.4],
                       fill=(255, 196, 96, 92))
        img = Image.alpha_composite(img, bloom.filter(
            ImageFilter.GaussianBlur(int(bh * 0.02))))

        out.append(img.resize((W, H), Image.LANCZOS))
    return out, [70] * frames


def load_gif_frames(path, target_h):
    """Read an animated GIF, keeping transparency, scaled to target height."""
    im = Image.open(path)
    frames, durs = [], []
    for raw in ImageSequence.Iterator(im):
        f = raw.convert("RGBA")
        s = target_h / float(f.height)
        frames.append(f.resize((max(1, int(f.width * s)), target_h), Image.LANCZOS))
        durs.append(max(40, int(raw.info.get("duration", 80))))
    return frames, durs


def reflection(img, drop=0.42, fade=0.26):
    """A fading mirror image, for the cake to stand on."""
    flip = img.transpose(Image.FLIP_TOP_BOTTOM)
    h = int(img.height * drop)
    flip = flip.crop((0, 0, img.width, h))
    ramp = np.linspace(fade, 0.0, h)[:, None]
    a = (np.array(flip.getchannel("A")).astype(np.float32) * ramp)
    flip.putalpha(Image.fromarray(a.astype(np.uint8)))
    return flip


# --------------------------------------------------------------------------
# ACT 3 - the cinematic engine
#
# Four animated layers overlap here (fireworks, drifting memories, the cake,
# the typography), so canvas items are the wrong tool: every moving item
# forces Tk to repaint everything under it. Instead the whole frame is
# composited in numpy/OpenCV and handed to Tk as ONE image per frame - the
# same path act 2 already uses at ~32fps. Heavy work (backdrop, sprites,
# text) happens once on the prep thread; per frame it is only blits.
# --------------------------------------------------------------------------
class Sprite:
    """An RGBA layer pre-split for fast alpha compositing.

    Blending is done in uint8 fixed point (dst*inv + pre), which OpenCV does
    with SIMD in a fraction of a millisecond; the float alpha is only kept
    when the sprite still has to fade in.
    """

    def __init__(self, img, keep_alpha=False):
        img = img.convert("RGBA")
        bbox = img.getchannel("A").getbbox()   # never blit empty margins
        self.off = (0, 0)
        if bbox:
            cx0, cy0 = img.width / 2.0, img.height / 2.0
            img = img.crop(bbox)
            self.off = (int((bbox[0] + bbox[2]) / 2.0 - cx0),
                        int((bbox[1] + bbox[3]) / 2.0 - cy0))
        arr = np.asarray(img)
        rgb = arr[..., :3]
        a = np.repeat(arr[..., 3:4].astype(np.float32) / 255.0, 3, axis=2)
        self.h, self.w = arr.shape[:2]
        self.pre = (rgb * a).astype(np.uint8)
        self.inv = ((1.0 - a) * 255).astype(np.uint8)
        self.rgb = rgb.copy() if keep_alpha else None
        self.a = a if keep_alpha else None

    def draw(self, dst, cx, cy, k=1.0):
        H, W = dst.shape[:2]
        cx += self.off[0]
        cy += self.off[1]
        x0, y0 = int(cx - self.w // 2), int(cy - self.h // 2)
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0, y0 = max(0, x0), max(0, y0)
        x1 = min(W, x0 + self.w - sx0)
        y1 = min(H, y0 + self.h - sy0)
        if x1 <= x0 or y1 <= y0:
            return
        sx1, sy1 = sx0 + (x1 - x0), sy0 + (y1 - y0)
        roi = dst[y0:y1, x0:x1]
        if k >= 0.999 or self.a is None:
            pre = self.pre[sy0:sy1, sx0:sx1]
            inv = self.inv[sy0:sy1, sx0:sx1]
        else:
            a = self.a[sy0:sy1, sx0:sx1] * k
            pre = (self.rgb[sy0:sy1, sx0:sx1] * a).astype(np.uint8)
            inv = ((1.0 - a) * 255).astype(np.uint8)
        cv2.add(cv2.multiply(roi, inv, scale=1 / 255.0), pre, dst=roi)


class Fireworks:
    """Procedural bursts on a low-resolution additive buffer.

    Particles are scattered into a quarter-size glow buffer that decays every
    frame - that decay IS the trail - then blurred and added over the frame.
    Doing it at full resolution in float32 cost 13ms; this costs ~3.5ms and
    supports any number of particles.
    """

    PALETTE = [(255, 214, 140), (255, 240, 214), (255, 176, 122),
               (168, 208, 255), (255, 158, 196), (214, 255, 226)]

    def __init__(self, W, H, div=4):
        self.W, self.H, self.div = W, H, div
        self.bw, self.bh = W // div, H // div
        self.buf = np.zeros((self.bh, self.bw, 3), np.uint8)
        self.pts = np.zeros((self.bh, self.bw, 3), np.uint8)
        n = 0
        self.x = np.zeros(n, np.float32)
        self.y = np.zeros(n, np.float32)
        self.vx = np.zeros(n, np.float32)
        self.vy = np.zeros(n, np.float32)
        self.life = np.zeros(n, np.float32)
        self.full = np.zeros(n, np.float32)
        self.col = np.zeros((n, 3), np.float32)
        self.next_burst = 0.6
        self.box = None          # active region in buffer coords
        self.idle = 0

    def burst(self, cx=None, cy=None):
        n = random.randint(38, 62)
        cx = random.uniform(self.bw * 0.12, self.bw * 0.88) if cx is None else cx
        cy = random.uniform(self.bh * 0.08, self.bh * 0.55) if cy is None else cy
        ang = np.random.uniform(0, 2 * math.pi, n).astype(np.float32)
        spd = np.random.uniform(8, 38, n).astype(np.float32)
        base = np.array(random.choice(self.PALETTE), np.float32)
        # held back so overlapping particles bloom instead of clipping to white
        tint = base * np.random.uniform(0.40, 0.62, (n, 1)).astype(np.float32)
        life = np.random.uniform(0.9, 1.9, n).astype(np.float32)
        self.x = np.concatenate([self.x, np.full(n, cx, np.float32)])
        self.y = np.concatenate([self.y, np.full(n, cy, np.float32)])
        self.vx = np.concatenate([self.vx, np.cos(ang) * spd])
        self.vy = np.concatenate([self.vy, np.sin(ang) * spd])
        self.life = np.concatenate([self.life, life])
        self.full = np.concatenate([self.full, life])
        self.col = np.concatenate([self.col, tint])

    def step(self, dt, t):
        self.next_burst -= dt
        if self.next_burst <= 0:
            self.burst()
            self.next_burst = random.uniform(0.55, 1.5)
        if len(self.x) == 0:
            return
        drag = math.pow(0.62, dt)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 11.0 * dt              # gravity, in buffer units
        self.vx *= drag
        self.vy *= drag
        self.life -= dt
        keep = self.life > 0
        if not keep.all():
            self.x, self.y = self.x[keep], self.y[keep]
            self.vx, self.vy = self.vx[keep], self.vy[keep]
            self.life, self.full = self.life[keep], self.full[keep]
            self.col = self.col[keep]

    def render(self, frame):
        """Blur + upscale only the live region.

        Blooming the whole buffer up to full resolution cost 4.7ms a frame
        even when a single burst was on screen. Tracking the lit box and
        scaling just that costs about a third of it, and between bursts the
        buffer is cleared so the work disappears entirely.
        """
        cv2.convertScaleAbs(self.buf, dst=self.buf, alpha=0.86)   # trails
        if len(self.x):
            self.idle = 0
            xi = self.x.astype(np.int32)
            yi = self.y.astype(np.int32)
            ok = (xi >= 0) & (xi < self.bw) & (yi >= 0) & (yi < self.bh)
            if ok.any():
                fade = np.clip(self.life[ok] / self.full[ok], 0, 1)[:, None]
                self.pts[:] = 0
                self.pts[yi[ok], xi[ok]] = (self.col[ok] * fade).astype(np.uint8)
                cv2.add(self.buf, self.pts, dst=self.buf)
                b = (xi[ok].min(), yi[ok].min(), xi[ok].max() + 1, yi[ok].max() + 1)
                self.box = b if self.box is None else (
                    min(self.box[0], b[0]), min(self.box[1], b[1]),
                    max(self.box[2], b[2]), max(self.box[3], b[3]))
        else:
            self.idle += 1
            if self.idle > 26:            # trails have decayed to nothing
                if self.box is not None:
                    self.buf[:] = 0
                    self.box = None
                return
        if self.box is None:
            return
        m = 14                             # room for the blur to spread
        x0 = max(0, self.box[0] - m); y0 = max(0, self.box[1] - m)
        x1 = min(self.bw, self.box[2] + m); y1 = min(self.bh, self.box[3] + m)
        if x1 <= x0 or y1 <= y0:
            return
        glow = cv2.GaussianBlur(self.buf[y0:y1, x0:x1], (0, 0), 2.1)
        d = self.div
        up = cv2.resize(glow, ((x1 - x0) * d, (y1 - y0) * d),
                        interpolation=cv2.INTER_LINEAR)
        roi = frame[y0 * d:y1 * d, x0 * d:x1 * d]
        cv2.add(roi, up, dst=roi)


class Memories:
    """The five photos as small glass panes drifting up through the scene."""

    def __init__(self, sprites, W, H, count=9):
        self.sprites = sprites
        self.W, self.H = W, H
        self.items = []
        for i in range(count):
            self.items.append({
                "s": sprites[i % len(sprites)],
                "x": random.uniform(W * 0.06, W * 0.94),
                "y": random.uniform(-H * 0.2, H * 1.2),
                "vy": random.uniform(9, 22),
                "sway": random.uniform(3, 11),
                "ph": random.uniform(0, 6.28),
                "spin": random.uniform(0.15, 0.45),
            })

    def step_draw(self, frame, dt):
        for it in self.items:
            it["y"] -= it["vy"] * dt
            it["ph"] += it["spin"] * dt
            it["x"] += math.sin(it["ph"]) * it["sway"] * dt
            if it["y"] < -it["s"].h:
                it["y"] = self.H + it["s"].h * 0.6
                it["x"] = random.uniform(self.W * 0.06, self.W * 0.94)
            it["s"].draw(frame, it["x"], it["y"])


class Glass:
    """A refined glass panel: whatever is behind it, heavily blurred.

    The blur is taken from the composited frame every tick, so the memory
    squares genuinely smear as they drift past underneath. Blurring a
    quarter-size copy and scaling back up is visually identical for this much
    blur and costs ~1.8ms instead of ~6ms.
    """

    def __init__(self, box, radius, veil=34, border=Sprite):
        self.x0, self.y0, self.x1, self.y1 = [int(v) for v in box]
        w, h = self.x1 - self.x0, self.y1 - self.y0
        self.w, self.h = w, h
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius,
                                               fill=255)
        m = np.asarray(mask)
        self.m_u8 = np.repeat(m[:, :, None], 3, axis=2)
        self.inv_u8 = 255 - self.m_u8
        self.m_f = self.m_u8.astype(np.float32) / 255.0
        self.veil = np.full((h, w, 3), veil, np.uint8)
        edge = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(edge)
        d.rounded_rectangle([0, 0, w - 1, h - 1], radius,
                            outline=(255, 255, 255, 70), width=2)
        d.rounded_rectangle([2, 2, w - 3, h - 3], radius - 2,
                            outline=(255, 236, 190, 26), width=1)
        self.edge = Sprite(edge.filter(ImageFilter.GaussianBlur(0.4)),
                           keep_alpha=True)
        self._blur = None
        self._age = 99

    def render(self, frame, k=1.0):
        if k <= 0.01:
            return
        roi = frame[self.y0:self.y1, self.x0:self.x1]
        # what is behind the glass drifts slowly, so refreshing the blur on
        # alternate frames is invisible and halves its cost
        self._age += 1
        if self._blur is None or self._age >= 2:
            small = cv2.resize(roi, (max(1, self.w // 4), max(1, self.h // 4)),
                               interpolation=cv2.INTER_AREA)
            small = cv2.GaussianBlur(small, (0, 0), 4)
            self._blur = cv2.resize(small, (self.w, self.h),
                                    interpolation=cv2.INTER_LINEAR)
            cv2.add(self._blur, self.veil, dst=self._blur)
            self._age = 0
        blurred = self._blur
        if k >= 0.999:
            m_u8, inv_u8 = self.m_u8, self.inv_u8
        else:
            m_u8 = (self.m_f * (255.0 * k)).astype(np.uint8)
            inv_u8 = 255 - m_u8
        cv2.add(cv2.multiply(roi, inv_u8, scale=1 / 255.0),
                cv2.multiply(blurred, m_u8, scale=1 / 255.0), dst=roi)
        self.edge.draw(frame, (self.x0 + self.x1) // 2,
                       (self.y0 + self.y1) // 2, k)


# --------------------------------------------------------------------------
# Threaded capture
# --------------------------------------------------------------------------
class CameraStream:
    """Grabs frames on a background thread.

    cap.read() blocks for ~32ms on a 30fps webcam. Calling it from the Tk
    callback would cap the whole UI at ~18fps; this way the UI always draws
    the newest frame and never waits on the camera.
    """

    def __init__(self, index):
        backend = cv2.CAP_DSHOW if os.name == "nt" else 0
        self.cap = cv2.VideoCapture(index, backend)
        if not self.cap.isOpened():
            self.cap.release()
            raise RuntimeError("camera %s unavailable" % index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        for _ in range(60):
            if self.frame is not None:
                break
            time.sleep(0.02)

    def _loop(self):
        while self.running:
            ok, f = self.cap.read()
            if ok and f is not None:
                with self.lock:
                    self.frame = f
            else:
                time.sleep(0.01)

    def read(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()

    def release(self, background=False):
        """DirectShow's cap.release() blocks ~280ms, which showed up as a
        freeze exactly on the cut out of act 1."""
        self.running = False

        def shut():
            self.thread.join(timeout=1.0)
            self.cap.release()

        if not background:
            shut()
            return None
        closer = threading.Thread(target=shut, daemon=True)
        closer.start()
        return closer


# --------------------------------------------------------------------------
# THE APP
# --------------------------------------------------------------------------
ctk.set_appearance_mode("dark")


class BirthdayApp(ctk.CTk):
    def __init__(self, cake_path=None, cake_downloaded=False):
        super().__init__()
        self.cake_path = cake_path
        self.cake_downloaded = cake_downloaded
        self.title("BIOMETRIC SCAN")
        self.sw = self.winfo_screenwidth()
        self.sh = self.winfo_screenheight()
        if FULLSCREEN:
            self.win_w, self.win_h = self.sw, self.sh
            self.attributes("-fullscreen", True)
        else:
            self.win_w, self.win_h = int(self.sw * 0.8), int(self.sh * 0.8)
            self.geometry("%dx%d" % (self.win_w, self.win_h))
        self.configure(fg_color="#05070C")

        for seq, fn in (("<Escape>", self.close), ("<q>", self.close),
                        ("<Q>", self.close), ("<space>", self.skip_ahead),
                        ("<r>", self.restart), ("<R>", self.restart)):
            self.bind(seq, lambda e, f=fn: f())
        self.protocol("WM_DELETE_WINDOW", self.close)

        self.cascade = load_cascade()
        self.cap = None
        self._cam_closing = None
        self.phase = None
        self.after_id = None
        self.photo = None
        self.faces = []
        self.frame_i = 0
        self.assets = None
        self.build_scan_ui()
        self.start_prep()
        self.start_scan()

    # ---------------- assets, prepared while act 1 plays ----------------
    def start_prep(self):
        """Render acts 2 and 3 on a worker thread.

        Both are heavy (five full-screen photo grades, the backdrop, the
        cake); doing it at the transitions froze the picture on the cut.
        It is all numpy/PIL, so it can happen while the scan is on screen -
        only the PhotoImage conversion has to be on the Tk thread.
        """
        self._prep = None
        W, H = self.win_w, self.win_h

        def work():
            try:
                self._prep = self.build_assets(W, H)
            except Exception as e:
                print("[!] Asset prep failed (%s) - building at transition." % e)
                self._prep = None

        threading.Thread(target=work, daemon=True).start()

    def build_assets(self, W, H):
        """All the numpy/PIL work. Thread-safe: no Tk calls in here."""
        rw = min(W, REEL_MAX_W)
        rh = int(round(H * rw / float(W)))
        vig = build_vignette(rw, rh)

        # its own cascade: act 1 is detecting on the Tk thread at the same
        # time, and one classifier is not safe to share across threads
        reel_cascade = load_cascade(quiet=True)
        slides = []
        for name in SLIDE_FILES:
            path = here(name)
            img = cv2.imread(path, cv2.IMREAD_COLOR) if os.path.exists(path) else None
            if img is None:
                print("[i] %s missing - skipping it in the reel." % name)
                continue
            slides.append(vintage(
                fit_photo(img, rw, rh, focus=face_focus(img, reel_cascade)), vig))
        if not slides:
            print("[!] No reel photos found - act 2 will be a title card.")
            slides = [self.missing_slide(rw, rh)]

        # ---- act 3 ------------------------------------------------------
        H3 = min(H, int(W / ACT3_ASPECT)) // 2 * 2      # cinematic frame
        cake_h = int(H3 * 0.38 * CAKE_SCALE)            # massive centrepiece
        cake_frames = cake_durs = None
        use_gif = (self.cake_path and os.path.exists(self.cake_path)
                   and (not self.cake_downloaded or PREFER_DOWNLOADED_CAKE))
        if use_gif:
            try:
                cake_frames, cake_durs = load_gif_frames(self.cake_path, cake_h)
                print("[+] Cake: %s (%d frames)" % (CAKE_GIF, len(cake_frames)))
            except Exception as e:
                print("[!] %s unreadable (%s) - rendering one." % (CAKE_GIF, e))
        if not cake_frames:
            cake_frames, cake_durs = render_3d_cake(cake_h)
            print("[+] Cake: built-in 3D render (%d frames)" % len(cake_frames))

        backdrop = build_backdrop(W, H3)
        cw, ch = cake_frames[0].width, cake_frames[0].height
        cx, cy = W // 2, int(H3 * 0.275)

        # cake + candle pool + reflection flattened into one sprite per frame,
        # so the per-frame cost in act 3 is a single blit
        glow = glow_image((int(cw * 1.5), int(ch * 1.5)), GOLD, 135)
        refl = reflection(cake_frames[0])
        pad = int(max(glow.width, glow.height) * 0.02) + 4
        bw = max(glow.width, cw, refl.width) + pad * 2
        bh = int(ch * 1.5 + refl.height * 0.9) + pad * 2
        mid = (bw // 2, int(bh * 0.42))
        refl_y = mid[1] + ch // 2 + refl.height // 2 - int(H3 * 0.008)

        def compose(frame_img, glow_k, k=1.0):
            plate = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            g = alpha_scale(glow, glow_k * k)
            plate.alpha_composite(g, (mid[0] - g.width // 2, mid[1] - g.height // 2))
            r = alpha_scale(refl, k)
            plate.alpha_composite(r, (mid[0] - r.width // 2, refl_y - r.height // 2))
            fimg = alpha_scale(frame_img, k)
            plate.alpha_composite(fimg, (mid[0] - fimg.width // 2,
                                         mid[1] - fimg.height // 2))
            return plate

        n = len(cake_frames)
        cake_seq = [compose(fr, 0.60 + 0.40 * (0.5 + 0.5 * math.sin(
            i / float(n) * 2 * math.pi))) for i, fr in enumerate(cake_frames)]
        cake_fade = [compose(cake_frames[0], 0.8, (k + 1) / 5.0) for k in range(5)]
        cake_xy = (cx, cy - mid[1] + bh // 2)

        # drifting memory panes
        memory = build_memory_panes(SLIDE_FILES, int(H3 * 0.19))

        # typography
        name_img = self.render_name(W, H3)
        name_xy = (W // 2, int(H3 * 0.645))
        tag_img = self.render_tag(W, H3)
        tag_xy = (W // 2, int(H3 * 0.722))
        para_img, para_lines = self.render_message(W, H3)
        para_xy = (W // 2, int(H3 * 0.855))
        glass_box = (0, 0, 10, 10)
        if para_img is not None:
            # the sprite already carries generous padding, so the panel is
            # its own bounds pulled in a hair - the copy sits well inside
            gw = para_img.width - int(H3 * 0.012)
            gh = para_img.height - int(H3 * 0.012)
            glass_box = (max(0, para_xy[0] - gw // 2), max(0, para_xy[1] - gh // 2),
                         min(W, para_xy[0] + gw // 2), min(H3, para_xy[1] + gh // 2))

        return {
            "size": (W, H3),
            "slides": slides, "grain": grain_bank(rw, rh),
            "backdrop_np": np.asarray(backdrop.convert("RGB")).copy(),
            "cake_seq": cake_seq, "cake_fade": cake_fade,
            "cake_durs": cake_durs, "cake_xy": cake_xy,
            "memory": memory,
            "name": name_img, "name_xy": name_xy,
            "tag": tag_img, "tag_xy": tag_xy,
            "para": para_img, "para_xy": para_xy, "glass_box": glass_box,
        }

    @staticmethod
    def missing_slide(w, h):
        img = np.zeros((h, w, 3), np.uint8)
        put(img, "NO PHOTOS FOUND", (int(w * 0.22), int(h * 0.48)),
            1.6 * (w / 1600.0), (200, 210, 230), 2)
        put(img, "drop 1.jpg .. 5.jpg next to this script",
            (int(w * 0.22), int(h * 0.56)), 0.8 * (w / 1600.0), (150, 160, 180), 1)
        return img

    @staticmethod
    def render_name(W, H):
        ttf = pick_ttf(["bahnschrift.ttf", "seguibl.ttf", "segoeuib.ttf",
                        "ariblk.ttf", "arialbd.ttf"])
        if ttf is None:
            return None
        size = fit_ttf_size(ttf, PARTY_NAME, W * 0.72, int(H * 0.115))
        return text_image(PARTY_NAME, ttf, size, GOLD_HI, GOLD,
                          glow_color=GOLD, glow_strength=1.25)

    @staticmethod
    def render_message(W, H):
        ttf = pick_ttf(["segoeui.ttf", "calibri.ttf", "arial.ttf"])
        if ttf is None:
            return None, 0
        size = max(15, int(H * 0.0245))
        return paragraph_image(MESSAGE, ttf, size, W * 0.56, TEXT_HI)

    @staticmethod
    def render_tag(W, H):
        ttf = pick_ttf(["segoeuil.ttf", "bahnschrift.ttf", "segoeui.ttf",
                        "arial.ttf"])
        if ttf is None:
            return None
        size = fit_ttf_size(ttf, PARTY_TAG, W * 0.24, int(H * 0.030))
        return text_image(PARTY_TAG, ttf, size, mix(MIST, TEXT_HI, 0.5), MIST,
                          glow_color=SPACE, glow_strength=1.6, track=1)

    # ---------------- ACT 1 : camera + glitch ----------------
    def build_scan_ui(self):
        self.scan_frame = ctk.CTkFrame(self, fg_color="#05070C", corner_radius=0)
        self.scan_frame.pack(fill="both", expand=True)
        self.video_label = tk.Label(self.scan_frame, bg="#05070C", bd=0,
                                    highlightthickness=0)
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

    def open_camera(self):
        closing = self._cam_closing
        if closing is not None and closing.is_alive():
            closing.join(timeout=2.0)
        try:
            return CameraStream(CAM_INDEX)
        except Exception as e:
            print("[!] No webcam on index %d (%s) - using a synthetic feed."
                  % (CAM_INDEX, e))
            return None

    def start_scan(self):
        self.phase = "scan"
        self.cap = self.open_camera()
        self.t0 = time.time()
        self.frame_i = 0
        self.faces = []
        self.tick()

    def grab_frame(self):
        if self.cap is not None:
            frame = self.cap.read()
            if frame is not None:
                return cv2.flip(frame, 1)
        f = np.zeros((720, 1280, 3), np.uint8)
        f[:] = (18, 12, 8)
        noise = np.random.randint(0, 26, (720, 1280, 1), np.uint8)
        f = cv2.add(f, cv2.merge([noise, noise, noise]))
        put(f, "NO CAMERA SIGNAL", (400, 380), 1.4, RED, 2)
        return f

    def tick(self):
        if self.phase not in ("scan", "glitch"):
            return
        t_start = time.perf_counter()
        now = time.time() - self.t0

        if self.phase == "scan" and now >= SCAN_SECONDS:
            self.phase = "glitch"
            self.beep(True)
        if self.phase == "glitch" and now >= SCAN_SECONDS + GLITCH_SECONDS:
            self.start_reel()
            return

        
        
        frame = self.grab_frame()
        h, w = frame.shape[:2]

        s = min(
            MAX_VIDEO_H / float(h),
            (self.sh * 0.98) / float(h),
            (self.sw * 0.98) / float(w)
        )

        if abs(s - 1.0) > 0.01:
            new_w = max(1, int(w * s))
            new_h = max(1, int(h * s))

            interpolation = (
                cv2.INTER_AREA if s < 1.0
                else cv2.INTER_CUBIC
            )

            frame = cv2.resize(
                frame,
                (new_w, new_h),
                interpolation=interpolation
            )


        # Face detection every 3rd frame, on a downscaled copy. Detecting at
        # full 720p costs ~80ms/call and tanks the frame rate; at 480px wide
        # it is ~20ms and just as reliable for a face filling the frame.
        self.frame_i += 1
        if self.cascade is not None and self.frame_i % 3 == 1:
            ds = DETECT_W / float(frame.shape[1])
            if ds < 1.0:
                small = cv2.resize(frame, None, fx=ds, fy=ds,
                                   interpolation=cv2.INTER_AREA)
            else:
                small, ds = frame, 1.0
            gray = cv2.equalizeHist(cv2.cvtColor(small, cv2.COLOR_BGR2GRAY))
            try:
                m = max(28, int(90 * ds))
                found = self.cascade.detectMultiScale(gray, 1.2, 5, minSize=(m, m))
            except cv2.error:
                found = []
            if len(found):
                x, y, fw, fh = max(found, key=lambda f: f[2] * f[3])
                box = (x / ds, y / ds, fw / ds, fh / ds)
                if self.faces:   # smooth, so the HUD box doesn't jitter on film
                    box = tuple(o + (n - o) * 0.5
                                for o, n in zip(self.faces[0], box))
                self.faces = [box]

        if self.phase == "scan":
            self.draw_hud(frame, now)
        else:
            frame = draw_glitch(frame, now - SCAN_SECONDS, GLITCH_SECONDS)

        self.show(frame)
        self.after_id = self.after(self.next_delay(t_start), self.tick)

    def show(self, frame, rgb=False):
        """Blit a frame into the shared label, reusing the PhotoImage.

        Building a fresh PhotoImage every frame (and re-configuring the
        label) costs ~7ms more per frame than pasting into the existing one.
        Act 3 composites straight to RGB, so it skips the colour convert.
        """
        
        # Expand the slideshow to the actual screen size.
        if self.phase == "reel":
            target_w, target_h = self.sw, self.sh

            if (frame.shape[1], frame.shape[0]) != (target_w, target_h):
                interpolation = (
                    cv2.INTER_CUBIC
                    if target_w > frame.shape[1]
                    else cv2.INTER_AREA
                )
                frame = cv2.resize(
                    frame,
                    (target_w, target_h),
                    interpolation=interpolation
                )

        if rgb:   # frombuffer wraps the array in place - no copy
            h, w = frame.shape[:2]
            pil = Image.frombuffer("RGB", (w, h), frame, "raw", "RGB", 0, 1)
        else:
            pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        if self.photo is None or (self.photo.width(), self.photo.height()) != pil.size:
            self.photo = ImageTk.PhotoImage(pil)
            self.video_label.configure(image=self.photo)
        else:
            self.photo.paste(pil)

    @staticmethod
    def next_delay(t_start, target_ms=FRAME_MS):
        """Sleep only for whatever is left of the frame budget.

        A fixed after(15) adds 15ms on top of the work, which is what
        actually capped the feed at ~18fps. The 5ms floor matters too:
        rescheduling with after(1) spins the Tcl timer queue hard enough to
        starve other events, keypresses included.
        """
        spent = (time.perf_counter() - t_start) * 1000.0
        return max(5, int(target_ms - spent))

    def draw_hud(self, img, now):
        h, w = img.shape[:2]
        pulse = 0.55 + 0.45 * math.sin(now * 7)

        if len(self.faces):
            x, y, fw, fh = self.faces[0]
            x, y = int(x - fw * 0.12), int(y - fh * 0.18)
            fw, fh = int(fw * 1.24), int(fh * 1.36)
        else:
            fw, fh = int(w * 0.30), int(h * 0.48)
            x, y = (w - fw) // 2, int(h * 0.18)
        x, y = max(2, x), max(2, y)
        fw, fh = min(fw, w - x - 2), min(fh, h - y - 2)

        corner_box(img, x, y, fw, fh, GREEN, 3)
        cv2.rectangle(img, (x, y), (x + fw, y + fh), (40, 90, 40), 1)
        sy = int(y + (fh - 2) * ((now * 0.9) % 1.0))
        cv2.line(img, (x + 4, sy), (x + fw - 4, sy), GREEN, 2, cv2.LINE_AA)
        cv2.line(img, (x + 4, sy), (x + fw - 4, sy), WHITE, 1, cv2.LINE_AA)
        ccx, ccy = x + fw // 2, y + fh // 2
        cv2.line(img, (ccx - 14, ccy), (ccx + 14, ccy), GREEN, 1)
        cv2.line(img, (ccx, ccy - 14), (ccx, ccy + 14), GREEN, 1)

        put(img, "TALIS-VISION v2.0  //  BIOMETRIC IDENTITY SCAN", (26, 44),
            0.72, GREEN, 1)
        put(img, "CAM 01   %s   LOCK: %s" % (
            time.strftime("%H:%M:%S"),
            "ACQUIRED" if len(self.faces) else "SEARCHING"),
            (26, 76), 0.6, CYAN if len(self.faces) else WHITE, 1)
        if pulse > 0.5:
            cv2.circle(img, (w - 44, 44), 10, RED, -1, cv2.LINE_AA)
        put(img, "REC", (w - 110, 52), 0.7, WHITE, 1)

        # keep all three readout lines clear of the progress bar at h-52
        ty = min(y + fh + 46, h - 140)
        if now < IDENTIFY_AT:
            dots = "." * (int(now * 4) % 4)
            put(img, "Scanning" + dots, (x, ty), 1.1, GREEN, 2)
            put(img, "ANALYSING FACIAL GEOMETRY", (x, ty + 34), 0.6, WHITE, 1)
        else:
            put(img, "%s Identified." % SCAN_NAME, (x, ty), 1.0, GREEN, 2)
            put(img, "Age: %s" % SCAN_AGE, (x, ty + 40), 1.0, CYAN, 2)
            put(img, "MATCH CONFIDENCE 99.7%   STATUS: TEENAGER",
                (x, ty + 74), 0.6, WHITE, 1)

        p = min(1.0, now / SCAN_SECONDS)
        bx, by, bw2, bh2 = 26, h - 52, w - 52, 16
        cv2.rectangle(img, (bx, by), (bx + bw2, by + bh2), (60, 60, 60), 1)
        cv2.rectangle(img, (bx + 2, by + 2),
                      (bx + 2 + int((bw2 - 4) * p), by + bh2 - 2), GREEN, -1)
        put(img, "SCAN %3d%%" % int(p * 100), (bx, by - 10), 0.6, WHITE, 1)

    # ---------------- ACT 2 : nostalgia reel ----------------
    def start_reel(self):
        self.phase = "reel"
        self.title("NOSTALGIA REEL")
        self.release_camera(background=True)
        if self._prep is None:                 # skipped ahead before prep ended
            self._prep = self.build_assets(self.win_w, self.win_h)
        self.assets = self._prep
        self.slides = self.assets["slides"]
        self.grain = self.assets["grain"]
        self.reel_t0 = time.time()
        self.reel_len = len(self.slides) * SLIDE_SECONDS
        self.reel_tick()

    def reel_tick(self):
        if self.phase != "reel":
            return
        t_start = time.perf_counter()
        t = time.time() - self.reel_t0
        if t >= self.reel_len:
            self.start_party()
            return

        n = len(self.slides)
        idx = min(n - 1, int(t / SLIDE_SECONDS))
        local = t - idx * SLIDE_SECONDS
        fade_at = SLIDE_SECONDS - FADE_SECONDS

        if local > fade_at:
            a = (local - fade_at) / FADE_SECONDS
            if idx + 1 < n:
                frame = cv2.addWeighted(self.slides[idx], 1.0 - a,
                                        self.slides[idx + 1], a, 0)
            else:
                frame = cv2.convertScaleAbs(self.slides[idx], alpha=1.0 - a)
        else:
            frame = self.slides[idx].copy()
            if local < 0.45:
                frame = cv2.convertScaleAbs(frame, alpha=min(1.0, local / 0.45))

        # cv2.add with a saturating cast is byte-identical to the numpy
        # int16 round-trip and about 11ms/frame cheaper at this size.
        grain = self.grain[self.frame_i % len(self.grain)]
        self.frame_i += 1
        frame = cv2.add(frame, grain, dtype=cv2.CV_8U)
        draw_camcorder(frame, t, idx, n)

        self.show(frame)
        self.after_id = self.after(self.next_delay(t_start), self.reel_tick)

    # ---------------- ACT 3 : the celebration ----------------
    def start_party(self):
        self.phase = "party"
        self.release_camera(background=True)
        self.configure(cursor="none", fg_color=SPACE)
        self.title("HAPPY 20th BIRTHDAY")
        if self.assets is None:
            self.assets = self._prep or self.build_assets(self.win_w, self.win_h)
        W, H = self.assets["size"]
        self.PW, self.PH = W, H
        self.video_label.configure(bg=SPACE)
        self.scan_frame.configure(fg_color=SPACE)
        self._build_scene(W, H)
        self._last_t = 0.0
        self.beep(False)
        self.pt0 = time.time()
        self.party_tick()

    def _build_scene(self, W, H):
        """Turn the prepped art into blit-ready sprites and layer objects."""
        a = self.assets
        self.frame_buf = np.empty((H, W, 3), np.uint8)
        self.backdrop_np = a["backdrop_np"]

        self.fw = Fireworks(W, H, FIREWORK_DIV)
        self.memories = Memories([Sprite(m) for m in a["memory"]], W, H,
                                 MEMORY_SQUARES)

        self.cake_seq = [Sprite(f) for f in a["cake_seq"]]
        self.cake_fade = [Sprite(f, keep_alpha=True) for f in a["cake_fade"]]
        self.cake_durs = a["cake_durs"]
        self.cake_xy = a["cake_xy"]
        self.cake_i = 0
        self.cake_next = 0.0

        self.name_spr = Sprite(a["name"], keep_alpha=True) if a["name"] else None
        self.name_xy = a["name_xy"]
        self.tag_spr = Sprite(a["tag"], keep_alpha=True) if a["tag"] else None
        self.tag_xy = a["tag_xy"]
        self.para_spr = Sprite(a["para"], keep_alpha=True) if a["para"] else None
        self.para_xy = a["para_xy"]
        self.glass = Glass(a["glass_box"], int(H * 0.028)) if a["para"] else None

    def party_tick(self):
        if self.phase != "party":
            return
        t_start = time.perf_counter()
        t = time.time() - self.pt0
        dt = min(0.05, max(0.0, t - self._last_t))
        self._last_t = t
        f = self.frame_buf

        # layer 1 - deep space, then fireworks blooming behind everything
        np.copyto(f, self.backdrop_np)
        self.fw.step(dt, t)
        self.fw.render(f)

        # layer 2 - memories drifting upward
        self.memories.step_draw(f, dt)

        # layer 3 - the centrepiece
        if t < 1.05:
            k = max(0.0, min(1.0, (t - 0.15) / 0.85))
            self.cake_fade[0].draw(f, self.cake_xy[0], self.cake_xy[1], k)
        else:
            if t >= self.cake_next:
                self.cake_i = (self.cake_i + 1) % len(self.cake_seq)
                self.cake_next = t + self.cake_durs[self.cake_i] / 1000.0
            self.cake_seq[self.cake_i].draw(f, self.cake_xy[0], self.cake_xy[1])

        # layer 4 - typography, on frosted glass that blurs the live frame
        if self.name_spr is not None:
            k = max(0.0, min(1.0, (t - 1.0) / 0.9))
            if k > 0:
                self.name_spr.draw(f, self.name_xy[0], self.name_xy[1], k)
        if self.tag_spr is not None:
            k = max(0.0, min(1.0, (t - 1.45) / 0.8))
            if k > 0:
                self.tag_spr.draw(f, self.tag_xy[0], self.tag_xy[1], k)
        if self.para_spr is not None:
            k = max(0.0, min(1.0, (t - 1.85) / 1.0))
            if k > 0:
                self.glass.render(f, k)
                self.para_spr.draw(f, self.para_xy[0], self.para_xy[1], k)

        self.show(f, rgb=True)
        self.after_id = self.after(self.next_delay(t_start), self.party_tick)

    # ---------------- lifecycle ----------------
    def skip_ahead(self):
        if self.phase in ("scan", "glitch"):
            self.start_reel()
        elif self.phase == "reel":
            self.start_party()

    def beep(self, error=False):
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND if error else winsound.MB_OK)
        except Exception:
            pass

    def release_camera(self, background=False):
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        if self.cap is not None:
            self._cam_closing = self.cap.release(background=background)
            self.cap = None

    def restart(self):
        self.release_camera()
        self.phase = None
        for child in self.winfo_children():
            child.destroy()
        self.configure(cursor="", fg_color="#05070C")
        self.photo = None       # the old video label is gone with its image
        self.build_scan_ui()    # prepared assets survive a replay
        self.start_scan()

    def close(self):
        self.phase = None
        self.release_camera()
        cv2.destroyAllWindows()
        self.destroy()


if __name__ == "__main__":
    print(__doc__)
    cake, downloaded = ensure_cake()
    if downloaded:
        print("[i] Using the built-in 3D cake for the celebration.")
        print("    %s was downloaded and kept alongside - set" % CAKE_GIF)
        print("    PREFER_DOWNLOADED_CAKE = True, or drop in your own file,")
        print("    to use it as the centrepiece instead.")
    BirthdayApp(cake_path=cake, cake_downloaded=downloaded).mainloop()
