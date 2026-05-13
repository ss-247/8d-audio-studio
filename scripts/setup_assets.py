"""
Download HRTF (.sofa) and soundfont (.sf2) assets required by 8D Studio.

Run once before launching the app:
    python scripts/setup_assets.py
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Asset definitions
# ---------------------------------------------------------------------------

ASSETS = [
    {
        "name": "MIT KEMAR HRTF (large pinna)",
        "urls": [
            "https://sofacoustics.org/data/database/mit/mit_kemar_large_pinna.sofa",
        ],
        "dest": Path("data/hrtf/mit_kemar.sofa"),
        "min_bytes": 1_000_000,  # > 1 MB
        "required": True,
        "manual_note": (
            "Download from: https://sofacoustics.org/data/database/mit/mit_kemar_large_pinna.sofa\n"
            "         Place at: data/hrtf/mit_kemar.sofa"
        ),
    },
    {
        "name": "GeneralUser GS SoundFont",
        "urls": [
            # Direct link to known working mirror of GeneralUser GS 1.471
            "https://www.dropbox.com/s/4x27l49kxcwamp5/GeneralUser_GS_v1.471.sf2?dl=1",
            # FluidR3 GM as fallback (same MIDI coverage, slightly larger)
            "https://keymusician01.s3.amazonaws.com/FluidR3_GM.zip",
        ],
        "dest": Path("data/soundfonts/generaluser.sf2"),
        "min_bytes": 10_000_000,  # > 10 MB
        "required": False,        # Only needed from Stage 5 (MIDI synthesis)
        "manual_note": (
            "Download GeneralUser GS from:\n"
            "           https://www.schristiancollins.com/generaluser.php\n"
            "         Unzip the .sf2 file and place it at: data/soundfonts/generaluser.sf2\n"
            "         (Not needed until Stage 5 — MIDI synthesis)"
        ),
    },
]

BASE_DIR = Path(__file__).resolve().parent.parent


def _progress_hook(block_num: int, block_size: int, total_size: int) -> None:
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 // total_size)
        bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
        print(f"\r  [{bar}] {pct:3d}%  ({downloaded/1e6:.1f} / {total_size/1e6:.1f} MB)", end="", flush=True)
    else:
        print(f"\r  Downloaded {downloaded/1e6:.1f} MB...", end="", flush=True)


def download_asset(asset: dict) -> bool:
    dest: Path = BASE_DIR / asset["dest"]
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and dest.stat().st_size >= asset["min_bytes"]:
        print(f"  [OK] {asset['name']} already present at {dest}")
        return True

    for url in asset["urls"]:
        print(f"\n  Downloading {asset['name']} from:\n  {url}")
        try:
            urllib.request.urlretrieve(url, dest, reporthook=_progress_hook)
            print()  # newline after progress bar
        except Exception as exc:
            print(f"\n  [WARN] Failed ({exc}), trying next URL...")
            if dest.exists():
                dest.unlink(missing_ok=True)
            continue

        size = dest.stat().st_size if dest.exists() else 0
        if size >= asset["min_bytes"]:
            print(f"  [OK] Saved to {dest} ({size/1e6:.1f} MB)")
            return True
        else:
            print(f"  [WARN] File too small ({size} bytes). Trying next URL...")
            dest.unlink(missing_ok=True)

    label = "[FAIL]" if asset["required"] else "[SKIP]"
    print(f"  {label} Could not download {asset['name']}.")
    print(f"         {asset['manual_note']}")
    return False


def main() -> None:
    print("=" * 60)
    print("  8D Studio — Asset Setup")
    print("=" * 60)

    required_ok = True
    for asset in ASSETS:
        ok = download_asset(asset)
        if not ok and asset["required"]:
            required_ok = False
        print()

    print("=" * 60)
    if required_ok:
        print("  Required assets ready.")
        print("  You can now run:  python main.py")
    else:
        print("  One or more REQUIRED assets failed to download.")
        print("  See messages above for manual download instructions.")
        sys.exit(1)


if __name__ == "__main__":
    main()
