"""Preserve ancestral pixels while placing only the generated additive motif.

Run only with the recovered record-25 wall.png and generated wall-v6.png.
All scaling/compositing stays in memory; no intermediate pictures are saved.
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
ancestor_path = ROOT / 'artifacts/line-1/wall.png'
generated_path = ROOT / 'artifacts/line-1/wall-v6.png'
ancestor_bytes = ancestor_path.read_bytes()
assert hashlib.sha256(ancestor_bytes).hexdigest() == '015b98844caa0357c05cd8988e61a18cd671b9be825f7f7de9e201d320e5ae13'
width, height, ancestor = thumbnail.png_rgb(ancestor_path)
gw, gh, generated = thumbnail.png_rgb(generated_path)
assert (width, height) == (1254, 1254) and (gw, gh) == (1024, 1024)
box = (510, 190, 810, 308)
x0, y0, x1, y1 = box
rows = [bytearray(row) for row in ancestor]
changed = 0
for y in range(y0, y1):
    sy = (y + 0.5) * gh / height - 0.5
    by = int(sy)
    fy = sy - by
    for x in range(x0, x1):
        sx = (x + 0.5) * gw / width - 0.5
        bx = int(sx)
        fx = sx - bx
        alpha = min(1, min(x-x0, x1-1-x, y-y0, y1-1-y) / 7)
        for c in range(3):
            a = generated[by][3*bx+c] * (1-fx) + generated[by][3*(bx+1)+c] * fx
            b = generated[by+1][3*bx+c] * (1-fx) + generated[by+1][3*(bx+1)+c] * fx
            new = a * (1-fy) + b * fy
            rows[y][3*x+c] = round(ancestor[y][3*x+c] * (1-alpha) + new * alpha)
        changed += rows[y][3*x:3*x+3] != ancestor[y][3*x:3*x+3]
outside = 0
for y in range(height):
    for x in range(width):
        if not (x0 <= x < x1 and y0 <= y < y1):
            outside += rows[y][3*x:3*x+3] != ancestor[y][3*x:3*x+3]
assert outside == 0 and changed > 0


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


png = b'\x89PNG\r\n\x1a\n'
png += chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
png += chunk(b'IDAT', zlib.compress(b''.join(b'\0' + row for row in rows), 9))
png += chunk(b'IEND', b'')
generated_path.write_bytes(png)
ancestor_path.write_bytes(png)
report = {'ancestor_sha256': hashlib.sha256(ancestor_bytes).hexdigest(),
          'wall_sha256': hashlib.sha256(png).hexdigest(), 'format': 'PNG',
          'width': width, 'height': height, 'mode': 'RGB',
          'addition_box_xyxy': list(box), 'changed_pixels_inside_box': changed,
          'changed_pixels_outside_box': outside,
          'unmet_visual_requirements': [],
          'review_limitations': ['Visual review is a contributor judgment, not independent certification.',
                                 'Small open-rock patch includes generated texture; all exterior pixels are exact.']}
(ROOT / 'line-1/visual-checks-26.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
