#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export.py — экспорт-зеркало канона (фаза 3, документ 10 §10.5).

Собирает полный снапшот: canon/ + _ledger.log + _rubrics.yml + dist/
в tar.gz + manifest.json (sha256 каждого файла — зеркало может
проверить целостность без доверия к транспорту).

НФТ (§10.6): полный экспорт канона <10 мин для 100k карточек —
у tar+sha256 это запас на порядки.

Использование:
  python3 export.py                 # -> dist/export/zh-lib-YYYY-MM-DD.tar.gz + manifest.json
  python3 export.py --out /tmp/zm   # в другую папку (например, на зеркало)
"""
import argparse
import datetime
import hashlib
import json
import os
import sys
import tarfile

ROOT = os.path.dirname(os.path.abspath(__file__))
INCLUDE_DIRS = ('canon', 'dist')
INCLUDE_FILES = ('_ledger.log', '_rubrics.yml', 'README.md')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def collect():
    files = []
    for rel in INCLUDE_FILES:
        p = os.path.join(ROOT, rel)
        if os.path.exists(p):
            files.append(rel)
    for d in INCLUDE_DIRS:
        base = os.path.join(ROOT, d)
        if not os.path.isdir(base):
            continue
        for dirpath, _, names in os.walk(base):
            for n in sorted(names):
                if n.endswith('.tar.gz'):  # не пакуем экспорт в экспорт
                    continue
                files.append(os.path.relpath(os.path.join(dirpath, n), ROOT))
    return sorted(files)


def main():
    ap = argparse.ArgumentParser(description='Экспорт-зеркало канона Живой Библиотеки')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist', 'export'))
    a = ap.parse_args()

    sys.path.insert(0, ROOT)
    from build import load_cards
    cards = load_cards()

    today = datetime.date.today().isoformat()
    os.makedirs(a.out, exist_ok=True)
    tar_path = os.path.join(a.out, 'zh-lib-%s.tar.gz' % today)

    files = collect()
    manifest = {
        'instance': 'zh-lib prototype',
        'exported_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'cards': len(cards),
        'card_versions': {c['id']: c.get('version', '1') for c in cards},
        'ledger_lines': sum(1 for _ in open(os.path.join(ROOT, '_ledger.log'), encoding='utf-8'))
        if os.path.exists(os.path.join(ROOT, '_ledger.log')) else 0,
        'files': {},
    }
    with tarfile.open(tar_path, 'w:gz') as tar:
        for rel in files:
            tar.add(os.path.join(ROOT, rel), arcname=rel)
            manifest['files'][rel] = {'sha256': sha256(os.path.join(ROOT, rel)),
                                      'bytes': os.path.getsize(os.path.join(ROOT, rel))}

    man_path = os.path.join(a.out, 'manifest.json')
    json.dump(manifest, open(man_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    size = os.path.getsize(tar_path)
    print('Экспорт готов: %s (%d байт, %d файлов, %d карточек)' % (tar_path, size, len(files), len(cards)))
    print('Манифест: %s (sha256 каждого файла)' % man_path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
