#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate.py — амнистия-миграция: перегон архива внешнего сообщества
в черновики карточек (фаза 3; документ 14, недели 3–6; документ 10 §10.4).

Вход: JSON-дамп форума/чата:
  {"community": "имя", "threads": [
      {"title": "...", "rubric": "formy/katalogi",
       "messages": [{"nick": "anna_p", "text": "..."}, ...]}]}

Каждый тред -> исходник сохраняется в inbox/migration/ (архив не теряется)
-> distill.py -> черновик карточки в inbox/ (уровень источника C —
«опыт сообщества», честная пометка). Ядро сообщества ревьюит черновики —
это и есть обучение хранителей на своём материале (A.2).

Канон не трогается: миграция, как и дистилляция, пишет только в inbox/.

Использование:
  python3 migrate.py inbox/migration-sample.json --keeper igor_s
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(ROOT, 'inbox')
MIG = os.path.join(INBOX, 'migration')
LEDGER = os.path.join(ROOT, '_ledger.log')

sys.path.insert(0, ROOT)
import distill as D  # noqa: E402


def next_ledger_id():
    best = 0
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding='utf-8'):
            m = re.search(r'ldg-(\d+)', line)
            if m:
                best = max(best, int(m.group(1)))
    return 'ldg-%04d' % (best + 1)


def main():
    ap = argparse.ArgumentParser(description='Миграция архива сообщества в черновики карточек')
    ap.add_argument('dump', help='JSON-дамп сообщества')
    ap.add_argument('--keeper', required=True, help='хранитель-принимающий (из ядра сообщества)')
    ap.add_argument('--rubric', help='рубрика по умолчанию, если у треда не задана')
    a = ap.parse_args()

    data = json.load(open(a.dump, encoding='utf-8'))
    community = data.get('community', os.path.basename(a.dump))
    threads = data.get('threads', [])
    if not threads:
        print('В дампе нет тредов.')
        return 1

    os.makedirs(MIG, exist_ok=True)
    created = []
    for i, t in enumerate(threads, 1):
        rubric = t.get('rubric') or a.rubric
        if not rubric:
            print('Тред %d: нет рубрики (ни в дампе, ни --rubric) — пропущен.' % i)
            continue
        # исходник треда сохраняется как есть — архив не теряется
        src_name = 'thread-%03d.md' % i
        src_path = os.path.join(MIG, src_name)
        with open(src_path, 'w', encoding='utf-8') as f:
            f.write('# %s\n# импортировано из: %s\n\n' % (t.get('title', src_name), community))
            for msg in t.get('messages', []):
                f.write('%s: %s\n' % (msg.get('nick', 'anon'), msg.get('text', '')))
        rc = D.distill(src_path, rubric, a.keeper, t.get('title'))
        if rc == 0:
            created.append(t.get('title', src_name))

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    open(LEDGER, 'a', encoding='utf-8').write(
        '%s | %s | migrate.py | community.migrated | community="%s" | threads=%d | drafts=%d | '
        'keeper=%s | comment="амнистия-миграция: черновики ждут ревью ядра"\n'
        % (ts, next_ledger_id(), community, len(threads), len(created), a.keeper))

    print('—' * 60)
    print('Миграция «%s»: тредов %d, черновиков создано %d.' % (community, len(threads), len(created)))
    print('Следующий шаг (A.2, недели 3–6): ядро ревьюит черновики — обучение хранителей.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
