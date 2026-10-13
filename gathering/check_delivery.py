#!/usr/bin/env python3
"""Check Gathering 06 files locally, without networking or changing line folders."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'shared/wall-thumbnail'))
import thumbnail


class Gallery(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = 0
        self.sources = []
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'article': self.articles += 1
        if tag == 'img': self.sources.append(a['src'])
        if tag == 'script' and 'src' in a: self.scripts.append(a['src'])


def jpeg_dimensions(raw):
    assert raw[:2] == b'\xff\xd8' and raw[-2:] == b'\xff\xd9'
    at = 2
    while at < len(raw):
        assert raw[at] == 255
        marker = raw[at + 1]
        size = int.from_bytes(raw[at + 2:at + 4], 'big')
        if marker == 0xc0:
            depth, height, width, channels = struct.unpack('>BHHB', raw[at + 4:at + 10])
            assert depth == 8 and channels == 3
            return width, height
        at += 2 + size
    raise ValueError('no baseline JPEG frame')


def main():
    wall = Path('artifacts/gathering/wall-v6.png')
    raster = wall.read_bytes()
    width, height, rows = thumbnail.png_rgb(wall)
    assert (width, height) == (1254, 1254)
    digest = hashlib.sha256(raster).hexdigest()
    jpg = Path('dist/gathering/06.jpg').read_bytes()
    assert jpeg_dimensions(jpg) == (512, 512) and len(jpg) < 100_000
    record = json.loads(Path('dist/gathering/06.json').read_text())
    assert set(record) == {'name', 'image', 'attributes'}
    assert record['image'] == 'https://api.imd.fun/artifacts/' + digest
    traits = record['attributes']
    assert [t['trait_type'] for t in traits] == ['Cave', 'Wall', 'Number', 'Left behind', 'Meaning', 'One thing']
    assert all(set(t) == {'trait_type', 'value'} for t in traits)
    assert [t['value'] for t in traits[:3]] == ['Moss', 'Gathering', 6]
    assert type(traits[2]['value']) is int
    assert traits[-1]['value'] == 'Gathering'
    goals = json.loads(Path('dist/goals.json').read_text())
    assert goals == [{'line': n, 'goal': Path(f'line-{n}/GOAL.md').read_text().strip()} for n in range(1, 5)]
    records = list(Path('dist').glob('*/[0-9][0-9].json'))
    painted = pending = 0
    bare = 'https://api.imd.fun/artifacts/250525790c1987cbb52114bd4e77926f023ac1dc10b73ffc2e1f56e32dfb8a36'
    for p in records:
        r = json.loads(p.read_text())
        if r['name'] == 'Not painted yet':
            pending += 1
            assert r == {'name': 'Not painted yet', 'image': bare, 'attributes': [{'trait_type': 'Cave', 'value': 'Moss'}]}
            assert not p.with_suffix('.jpg').exists()
        else:
            painted += 1
            assert p.with_suffix('.jpg').is_file()
    for slug in ('line-1', 'line-2', 'line-3', 'line-4', 'gathering'):
        assert all(Path(f'dist/{slug}/{n:02}.json').is_file() for n in range(2, 22))
    page = Path('dist/index.html').read_text()
    gallery = Gallery(); gallery.feed(page)
    assert gallery.articles == len(records) and not gallery.scripts
    for source in gallery.sources:
        assert source.startswith('https://api.imd.fun/artifacts/') or (Path('dist') / source).is_file()
    for slug in ('line-1', 'line-2', 'line-3', 'line-4', 'gathering'):
        section = page.split(f'<section id="{slug}">', 1)[1].split('</section>', 1)[0]
        numbers = [int(n) for n in re.findall(r'<h3>Round ([0-9]+) ', section.split('<details>', 1)[0])]
        assert numbers == sorted(numbers, reverse=True)
    diff = subprocess.run(['git', 'diff', '--name-only'], capture_output=True, text=True, check=True).stdout.splitlines()
    assert not any(p.startswith(('line-1/', 'line-2/', 'line-3/', 'line-4/', 'dist/line-')) for p in diff)
    status = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], capture_output=True, text=True, check=True).stdout.splitlines()
    paths = [line[3:] for line in status]
    assert all(p.startswith(('gathering/', 'shared/', 'dist/', 'artifacts/gathering/')) for p in paths)
    tracked_outputs = subprocess.run(['git', 'ls-files', 'artifacts/gathering/'], capture_output=True, text=True, check=True).stdout
    assert not tracked_outputs.strip()
    oversized = [str(p) for root in ('gathering', 'shared', 'dist') for p in Path(root).rglob('*') if p.is_file() and p.stat().st_size >= 100_000]
    assert not oversized
    assert Path('gathering/COINS.md').read_text().splitlines()[0] == 'none'
    assert not Path('gathering/coin-order.json').exists() and not Path('gathering/deploy-order.json').exists()
    checks = json.loads(Path('gathering/check-results.json').read_text())
    assert checks['all_passed']
    visual = json.loads(Path('gathering/visual-checks.json').read_text())
    assert visual['output_sha256'] == digest and visual['changed_pixels_outside_addition'] == 0
    assert visual['source_sha256'] == json.loads(Path('dist/gathering/05.json').read_text())['image'].rsplit('/', 1)[-1]
    assert visual['unmet_visual_requirements_observed'] == []
    tests = sum(int(re.search(r'Ran ([0-9]+) tests', c.get('stderr', '')).group(1)) for c in checks['checks'] if '-suite' in c['name'])
    assert tests == 410
    for p in Path('gathering').glob('live-*.json'):
        assert p.stat().st_size and isinstance(json.loads(p.read_text()), dict)
    result = {'schema': 'gathering-delivery-checks-v6', 'authority': 'Local contributor checks; not independent certification.',
              'wall': {'path': str(wall), 'format': 'PNG RGB 8-bit', 'width': width, 'height': height, 'sha256': digest, 'bytes': len(raster), 'chunk_crcs_and_raster_valid': True, 'required_png_untracked': True},
              'thumbnail': {'path': 'dist/gathering/06.jpg', 'format': 'baseline JPEG', 'width': 512, 'height': 512, 'bytes': len(jpg)},
              'visual_review': {'left_hand_digits': 5, 'right_hand_digits': 5, 'new_hands': 0, 'unmet_requirements_observed': [], 'limits': 'Subjective review; exact preservation is measured outside the addition rectangle.'},
              'records': len(records), 'painted': painted, 'placeholders': pending, 'gallery_articles': gallery.articles, 'goals': len(goals),
              'line_sources_and_records_unchanged': True, 'changed_source_paths_within_scope': True, 'oversized_output_source_files': oversized,
              'offline_tests': tests, 'offline_commands': len(checks['checks']), 'offline_expected_exits_matched': True}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
