#!/usr/bin/env python3
"""Composite one in-memory RGBA pigment insert onto Pepe 25's exact wall.

Usage: finish_wall_26.py < generated-insert.png
The insert is deliberately consumed from stdin and never saved in the workspace.
"""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import zlib

ROOT = Path(__file__).resolve().parents[1]
WALL = ROOT / 'artifacts' / 'line-2' / 'wall-v6.png'
SOURCE_SHA256 = 'fc1ff282e8e29d7102002b0496f76b58bc0ba94515ebc4565dbaf2820ac4e069'
PLACE_X, PLACE_Y, PLACE_W, PLACE_H = 900, 795, 190, 145


def decode(blob):
    if blob[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('expected PNG')
    pos, header, packed = 8, None, bytearray()
    while pos < len(blob):
        length = int.from_bytes(blob[pos:pos+4], 'big')
        kind, data = blob[pos+4:pos+8], blob[pos+8:pos+8+length]
        if len(data) != length or zlib.crc32(kind + data) != int.from_bytes(blob[pos+8+length:pos+12+length], 'big'):
            raise ValueError('bad PNG chunk')
        if kind == b'IHDR':
            header = struct.unpack('>IIBBBBB', data)
        elif kind == b'IDAT':
            packed.extend(data)
        elif kind == b'IEND':
            break
        pos += length + 12
    if header is None:
        raise ValueError('missing PNG header')
    width, height, depth, color, comp, filt, interlace = header
    if depth != 8 or color not in (2, 6) or comp or filt or interlace:
        raise ValueError('need 8-bit noninterlaced RGB/RGBA PNG')
    channels, stride = (3 if color == 2 else 4), width * (3 if color == 2 else 4)
    raw = zlib.decompress(packed)
    if len(raw) != (stride + 1) * height:
        raise ValueError('bad scanlines')
    previous, rows = bytearray(stride), []
    for y in range(height):
        mode, row = raw[y*(stride+1)], bytearray(raw[y*(stride+1)+1:(y+1)*(stride+1)])
        if mode not in range(5):
            raise ValueError('bad filter')
        for x in range(stride):
            a, b = (row[x-channels] if x >= channels else 0), previous[x]
            c = previous[x-channels] if x >= channels else 0
            if mode == 1: predictor = a
            elif mode == 2: predictor = b
            elif mode == 3: predictor = (a+b)//2
            elif mode == 4:
                p = a+b-c
                predictor = min((a, b, c), key=lambda n: abs(p-n))
            else: predictor = 0
            row[x] = (row[x] + predictor) & 255
        rows.append(bytes(row)); previous = row
    return width, height, channels, rows


def encode(width, height, rows):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b''.join(b'\0'+row for row in rows), 9)) + chunk(b'IEND', b''))


def composite(base, mark):
    mw, mh, channels, markrows = mark
    if channels != 4:
        raise ValueError('generated insert needs RGBA transparency')
    visible = [(x, y) for y, row in enumerate(markrows) for x in range(mw) if row[4*x+3] > 16]
    if not visible:
        raise ValueError('insert is fully transparent')
    x0, x1 = min(x for x, _ in visible), max(x for x, _ in visible)+1
    y0, y1 = min(y for _, y in visible), max(y for _, y in visible)+1
    result = [bytearray(row) for row in base]
    for dy in range(PLACE_H):
        sy0, sy1 = y0 + dy*(y1-y0)/PLACE_H, y0 + (dy+1)*(y1-y0)/PLACE_H
        for dx in range(PLACE_W):
            sx0, sx1 = x0 + dx*(x1-x0)/PLACE_W, x0 + (dx+1)*(x1-x0)/PLACE_W
            weight_total, alpha_total, rgb = 0.0, 0.0, [0.0, 0.0, 0.0]
            for sy in range(math.floor(sy0), math.ceil(sy1)):
                wy = max(0, min(sy1, sy+1)-max(sy0, sy))
                for sx in range(math.floor(sx0), math.ceil(sx1)):
                    weight = wy * max(0, min(sx1, sx+1)-max(sx0, sx))
                    alpha = markrows[sy][4*sx+3] / 255
                    weight_total += weight
                    alpha_total += weight * alpha
                    for c in range(3): rgb[c] += markrows[sy][4*sx+c] * weight * alpha
            if not alpha_total:
                continue
            alpha = min(1, (alpha_total / weight_total) ** .7) * .94
            out = result[PLACE_Y+dy]; offset = 3*(PLACE_X+dx)
            for c in range(3): out[offset+c] = round(out[offset+c]*(1-alpha) + rgb[c]/alpha_total*alpha)
    return [bytes(row) for row in result], [x0, y0, x1, y1]


def main():
    source = WALL.read_bytes()
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('expected the verified Pepe 25 wall; refusing to paint another source')
    width, height, channels, base = decode(source)
    if (width, height, channels) != (1254, 1254, 3):
        raise ValueError('unexpected inherited wall dimensions')
    result, bounds = composite(base, decode(sys.stdin.buffer.read()))
    for y, (old, new) in enumerate(zip(base, result)):
        if y < PLACE_Y or y >= PLACE_Y + PLACE_H:
            assert old == new
        else:
            assert old[:PLACE_X*3] == new[:PLACE_X*3]
            assert old[(PLACE_X+PLACE_W)*3:] == new[(PLACE_X+PLACE_W)*3:]
    output = encode(width, height, result)
    WALL.write_bytes(output)
    changed = sum(1 for old, new in zip(base, result)
                  for offset in range(0, len(old), 3)
                  if old[offset:offset+3] != new[offset:offset+3])
    print(json.dumps({'source_sha256': SOURCE_SHA256, 'output_sha256': hashlib.sha256(output).hexdigest(),
                      'dimensions': [width, height], 'insert_alpha_bounds': bounds,
                      'placement_rectangle': [PLACE_X, PLACE_Y, PLACE_W, PLACE_H],
                      'changed_pixels': changed, 'outside_placement_unchanged': True,
                      'output_bytes': len(output)}))


if __name__ == '__main__':
    main()
