"""
Applica auto_trim_border a tutte le foto già presenti nel CMS.
Sovrascrive i file originali e rigenera le thumbs.
"""
import os, json
from pathlib import Path
from PIL import Image
import numpy as np

BASE   = Path(__file__).parent
UPLOAD = BASE / 'uploads'
DATA   = BASE / 'data' / 'uploads'

def auto_trim_border(im, threshold=18, min_strip=2, max_strip_pct=0.08):
    arr = np.array(im.convert('RGB'), dtype=np.float32)
    h, w = arr.shape[:2]
    max_rows = int(h * max_strip_pct)
    max_cols = int(w * max_strip_pct)

    def row_is_border(row): return float(row.std()) < threshold
    def col_is_border(col): return float(col.std()) < threshold

    top = 0
    while top < max_rows and row_is_border(arr[top]): top += 1
    bottom = h
    while (h - bottom) < max_rows and row_is_border(arr[bottom - 1]): bottom -= 1
    left = 0
    while left < max_cols and col_is_border(arr[:, left]): left += 1
    right = w
    while (w - right) < max_cols and col_is_border(arr[:, right - 1]): right -= 1

    if top >= min_strip or (h - bottom) >= min_strip or left >= min_strip or (w - right) >= min_strip:
        return im.crop((left, top, right, bottom)), (top, h-bottom, left, w-right)
    return im, (0, 0, 0, 0)

def process_dir(directory):
    directory = Path(directory)
    if not directory.exists():
        return
    for fpath in directory.iterdir():
        if fpath.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            continue
        if 'thumb' in fpath.name:
            continue
        try:
            with Image.open(str(fpath)) as im:
                if im.mode not in ('RGB',):
                    im = im.convert('RGB')
                orig_size = im.size
                trimmed, borders = auto_trim_border(im)
                if trimmed.size != orig_size:
                    print(f"  TRIMMED {fpath.name}: {orig_size} → {trimmed.size} (bordi: top={borders[0]}, bottom={borders[1]}, left={borders[2]}, right={borders[3]})")
                    trimmed.save(str(fpath), 'JPEG', quality=88, optimize=True)
                    # Rigenera thumb
                    thumb_path = fpath.parent / 'thumbs' / ('thumb_' + fpath.stem + '.jpg')
                    if thumb_path.parent.exists():
                        w, h = trimmed.size
                        ar = w / h
                        tw = 400
                        th = int(400 / ar)
                        thumb = trimmed.copy()
                        thumb.thumbnail((tw, th), Image.LANCZOS)
                        thumb.save(str(thumb_path), 'JPEG', quality=82)
                else:
                    print(f"  ok      {fpath.name}: nessun bordo rilevato")
        except Exception as e:
            print(f"  ERROR   {fpath.name}: {e}")

print("=== Trim foto in uploads/ ===")
process_dir(UPLOAD)

print("\n=== Trim foto in data/uploads/ (sottocartelle) ===")
if DATA.exists():
    for subdir in DATA.iterdir():
        if subdir.is_dir():
            print(f"\n  [{subdir.name}]")
            process_dir(subdir)

print("\nDone.")
