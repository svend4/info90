#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
deadman.py — dead man's switch (фаза 3, документ 10 §10.5).

Если инстанс не подавал признаков жизни N дней (build.py обновляет
_heartbeat при каждой сборке), автоматический пайплайн публикует
полный tarball канона + журнала на заранее настроенные адреса
из _mirrors.yml (в боевом варианте — IPFS/HTTP-зеркала;
в прототипе — каталоги-приёмники, контракт тот же).

Знание не должно умирать вместе с хостингом.

Использование:
  python3 deadman.py --days 30          # проверка; при молчании — публикация
  python3 deadman.py --days 30 --check  # только проверка (exit 1, если пора публиковать)
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT = os.path.join(ROOT, '_heartbeat')
MIRRORS = os.path.join(ROOT, '_mirrors.yml')
LEDGER = os.path.join(ROOT, '_ledger.log')


def read_heartbeat():
    if not os.path.exists(HEARTBEAT):
        return None
    raw = open(HEARTBEAT, encoding='utf-8').read().strip()
    try:
        return datetime.date.fromisoformat(raw[:10])
    except ValueError:
        return None


def read_mirrors():
    """_mirrors.yml: строки вида '- /путь/к/зеркалу'."""
    out = []
    if not os.path.exists(MIRRORS):
        return out
    for line in open(MIRRORS, encoding='utf-8'):
        line = line.strip()
        if line.startswith('- '):
            out.append(line[2:].strip().strip('"'))
    return [m for m in out if m and not m.startswith('#')]


def next_ledger_id():
    best = 0
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding='utf-8'):
            m = re.search(r'ldg-(\d+)', line)
            if m:
                best = max(best, int(m.group(1)))
    return 'ldg-%04d' % (best + 1)


def main():
    ap = argparse.ArgumentParser(description="Dead man's switch Живой Библиотеки")
    ap.add_argument('--days', type=int, default=30, help='тишина в днях до срабатывания')
    ap.add_argument('--check', action='store_true', help='только проверить, не публиковать')
    a = ap.parse_args()

    hb = read_heartbeat()
    today = datetime.date.today()
    if hb is None:
        print('[RED   ] _heartbeat отсутствует или не читается — признаков жизни нет')
        silent = a.days + 1
    else:
        silent = (today - hb).days
        z = 'GREEN' if silent <= a.days else 'RED'
        print(f'[{z:6}] последний признак жизни: {hb} ({silent} дн. назад, порог {a.days})')

    if silent <= a.days:
        print('Инстанс жив. Переключатель не срабатывает.')
        return 0

    print('ТИШИНА ПРЕВЫШЕНА. Знание не должно умереть вместе с хостингом.')
    if a.check:
        print('Режим --check: публикация не выполняется (exit 1 = пора публиковать).')
        return 1

    mirrors = read_mirrors()
    if not mirrors:
        print('[RED   ] _mirrors.yml пуст — публиковать некуда! Настройте зеркала заранее.')
        return 1

    # 1. полный экспорт канона + журнала
    export_dir = os.path.join(ROOT, 'dist', 'export')
    rc = subprocess.call([sys.executable, os.path.join(ROOT, 'export.py'), '--out', export_dir])
    if rc != 0:
        print('Экспорт не удался — публикация отменена.')
        return 1

    # 2. публикация на зеркала (прототип: каталоги-приёмники)
    published = []
    for m in mirrors:
        try:
            os.makedirs(m, exist_ok=True)
            for f in os.listdir(export_dir):
                shutil.copy2(os.path.join(export_dir, f), os.path.join(m, f))
            published.append(m)
            print('[GREEN ] опубликовано -> %s' % m)
        except OSError as e:
            print('[RED   ] зеркало %s недоступно: %s' % (m, e))

    # 3. запись в журнал (публично: переключатель сработал)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    open(LEDGER, 'a', encoding='utf-8').write(
        '%s | %s | deadman.py | deadman.triggered | silent_days=%d | mirrors=%d | '
        'comment="инстанс молчал >%d дн.; канон опубликован на зеркала"\n'
        % (ts, next_ledger_id(), silent, len(published), a.days))
    print('Журнал: deadman.triggered записано. Опубликовано зеркал: %d/%d.' % (len(published), len(mirrors)))
    return 0 if published else 1


if __name__ == '__main__':
    sys.exit(main())
