"""Safe launcher for Pavley's 20th birthday project.

The full animation remains in birthday_upgrade_original.py. This launcher
keeps the original visuals, enables Windows high-DPI awareness so fullscreen
matches the physical monitor, and falls back safely when OpenCV does not
expose cv2.CascadeClassifier.

Run with: py -3.14 birthday_upgrade.py
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import ctypes
import sys


def enable_windows_dpi_awareness():
    """Avoid Windows DPI virtualization making fullscreen only a quarter-screen."""
    if sys.platform != "win32":
        return

    # Must run before the original module imports/creates any Tk windows.
    try:
        # PROCESS_PER_MONITOR_DPI_AWARE
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        print("[i] Windows high-DPI awareness enabled.")
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            print("[i] Windows DPI awareness enabled (system-aware fallback).")
        except Exception as exc:
            print(f"[i] Could not change Windows DPI mode: {exc}")


enable_windows_dpi_awareness()

BASE_DIR = Path(__file__).resolve().parent
ORIGINAL_FILE = BASE_DIR / "birthday_upgrade_original.py"

if not ORIGINAL_FILE.is_file():
    raise FileNotFoundError(
        f"Could not find the original birthday animation: {ORIGINAL_FILE}"
    )

spec = spec_from_file_location("birthday_upgrade_original", ORIGINAL_FILE)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load birthday animation from {ORIGINAL_FILE}")

birthday = module_from_spec(spec)
sys.modules[spec.name] = birthday
spec.loader.exec_module(birthday)

# Personal settings for Pavley's birthday project.
birthday.SCAN_NAME = "Pavley Mousa"
birthday.SCAN_AGE = "19.99"
birthday.PARTY_NAME = "Pavley Mousa"
birthday.PARTY_TAG = "@eng.bevo"
birthday.SLIDE_FILES = [f"{index}.jpg" for index in range(1, 16)]
birthday.FULLSCREEN = True
birthday.MESSAGE = (
    "Twenty years of memories, lessons, and moments have shaped who I am. "
    "I'm grateful for everyone who has walked beside me, every challenge "
    "that made me stronger, and every blessing along the way. Here's to a "
    "new chapter filled with hope, purpose, unforgettable memories, and "
    "dreams worth chasing. The best is yet to come."
)

# OpenCV 5 builds may not expose CascadeClassifier at all. In that case, let
# the existing HUD use its centered target box instead of crashing at startup.
_original_load_cascade = birthday.load_cascade


def safe_load_cascade(quiet=False):
    if not hasattr(birthday.cv2, "CascadeClassifier"):
        if not quiet:
            print(
                "[i] This OpenCV build has no CascadeClassifier API; "
                "using the centered scan box instead."
            )
        return None

    try:
        return _original_load_cascade(quiet=quiet)
    except Exception as exc:
        if not quiet:
            print(f"[i] Face detection unavailable ({exc}); using a centered scan box.")
        return None


birthday.load_cascade = safe_load_cascade


def main():
    print("Pavley's 20th Birthday — safe launcher")
    print("[i] Slideshow order: " + ", ".join(birthday.SLIDE_FILES))
    print("[i] Fullscreen is enabled. SPACE skips an act, R restarts, ESC/Q exits.")
    print("[i] If photos are missing, the reel will skip them.")
    cake, downloaded = birthday.ensure_cake()
    if downloaded:
        print("[i] Using the built-in 3D cake by default; see PREFER_DOWNLOADED_CAKE.")
    birthday.BirthdayApp(cake_path=cake, cake_downloaded=downloaded).mainloop()


if __name__ == "__main__":
    main()
