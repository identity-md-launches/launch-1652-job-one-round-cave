"""Assemble only the generated new motif; preserve every ancestor pixel outside it.

Artifact production helper, not a Code Review runtime dependency. It reads the
verified record-25 wall.png and the generated wall-v6.png, and saves no previews.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import zlib

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('thumbnail', ROOT / 'shared/wall-thumbnail/thumbnail.py')
thumbnail = importlib.util.module_from_spec(spec)
spec.loader.exec_module(thumbnail)
ancestor_path = ROOT / 'artifacts/line-3/wall.png'
generated_path = ROOT / 'artifacts/line-3/wall-v6.png'
ancestor_bytes = ancestor_path.read_bytes()
assert hashlib.sha256(ancestor_bytes).hexdigest() == '4a8166436a1cc3fa4931f384f29fad0d9cbb76b983a515a79c3d77306aabc272'
width, height, ancestor = thumbnail.png_rgb(ancestor_path)
gw, gh, generated = thumbnail.png_rgb(generated_path)
assert (width, height) == (1254, 1254) and (gw, gh) == (1254, 1254)
# The editor moved an ancestor. Retain only its new head and ring, reduced
# proportionally to fit a genuinely unpainted gap in the original wall.
source_box = (748, 594, 1023, 721)
box = (798, 582, 975, 664)
x0, y0, x1, y1 = box
sx0, sy0, sx1, sy1 = source_box
rows = [bytearray(row) for row in ancestor]
changed = 0
for y in range(y0, y1):
    sy = sy0 + (y-y0+0.5) * (sy1-sy0) / (y1-y0) - 0.5
    by = int(sy)
    fy = sy-by
    for x in range(x0, x1):
        sx = sx0 + (x-x0+0.5) * (sx1-sx0) / (x1-x0) - 0.5
        bx = int(sx)
        fx = sx-bx
        alpha = min(1, min(x-x0, x1-1-x, y-y0, y1-1-y) / 4)
        for c in range(3):
            a = generated[by][3*bx+c]*(1-fx) + generated[by][3*(bx+1)+c]*fx
            b = generated[by+1][3*bx+c]*(1-fx) + generated[by+1][3*(bx+1)+c]*fx
            new = a*(1-fy)+b*fy
            rows[y][3*x+c] = round(ancestor[y][3*x+c]*(1-alpha)+new*alpha)
        changed += rows[y][3*x:3*x+3] != ancestor[y][3*x:3*x+3]
outside = sum(rows[y][3*x:3*x+3] != ancestor[y][3*x:3*x+3]
              for y in range(height) for x in range(width)
              if not (x0 <= x < x1 and y0 <= y < y1))
assert outside == 0 and changed > 0


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))


png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(b''.join(b'\0'+row for row in rows), 9))
png += chunk(b'IEND', b'')
generated_path.write_bytes(png)
ancestor_path.write_bytes(png)
report = {'ancestor_sha256': hashlib.sha256(ancestor_bytes).hexdigest(),
          'wall_sha256': hashlib.sha256(png).hexdigest(), 'format': 'PNG',
          'dimensions': [width, height], 'mode': 'RGB', 'wall_bytes': len(png),
          'addition_box_xyxy': list(box), 'generated_motif_crop_xyxy': list(source_box),
          'changed_pixels_inside_box': changed, 'changed_pixels_outside_box': outside,
          'manual_review_pending': True}
(ROOT / 'line-3/visual-checks-26.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
