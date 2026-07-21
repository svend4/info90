#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
digest.py — еженедельный дайджест-смотр (документ 13, ритуалы;
документ 15 §15.2 — open-вопросы как backlog рубрик).

Собирает за неделю: события журнала, изменения канона, открытые
вопросы, сигналы «полезно», зоны здоровья — в digest/YYYY-Www.md.
Ритуал: хранители читают в начале недели, 15 минут.

Использование:
  python3 digest.py             # дайджест текущей недели -> digest/
  python3 digest.py --days 14   # за другой период
  python3 digest.py --person igor_s   # след человека в журнале (§18.9.5: фильтр, не агрегат)
"""
import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, '_ledger.log')
QUESTIONS = os.path.join(ROOT, 'questions')
USEFUL = os.path.join(ROOT, 'threads', '_useful.log')
DIGEST = os.path.join(ROOT, 'digest')


def person_digest(nick):
    """Дайджест по человеку (документ 18 §18.9.5): выборка первичных записей
    журнала — НЕ числовая репутация. Читающий видит те же записи, только меньше."""
    if not os.path.exists(LEDGER):
        print('Журнал пуст.')
        return 1
    actor, mention = [], []
    pat_actor = re.compile(r'\| (author|keeper|gardener|system)?:?' + re.escape(nick) + r' \|')
    pat_keys = re.compile(r'(keeper|voucher|by|candidate|initiator|quorum)=[^|]*\b' + re.escape(nick) + r'\b')
    for line in open(LEDGER, encoding='utf-8'):
        line = line.rstrip('\n')
        if pat_actor.search(line):
            actor.append(line)
        elif pat_keys.search(line):
            mention.append(line)
    today = datetime.date.today().isoformat()
    out = ['# След участника %s в журнале власти (по состоянию на %s)' % (nick, today), '',
           '> Фильтр журнала, а не агрегат (§18.9.5): здесь первичные записи —',
           '> с именами, датами и причинами. Выводы делает читающий, не скрипт.', '']
    out.append('## Действия (%s)' % len(actor))
    out.append('')
    out += ['- `%s`' % l for l in actor] or ['- нет']
    out.append('')
    out.append('## Упоминания в действиях других (%s)' % len(mention))
    out.append('')
    out += ['- `%s`' % l for l in mention] or ['- нет']
    out.append('')
    out.append('---')
    out.append('*Собрано digest.py --person. Записи не сведены в число сознательно (документ 18).*')
    os.makedirs(DIGEST, exist_ok=True)
    path = os.path.join(DIGEST, 'person-%s.md' % nick)
    open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('След участника: %s' % os.path.relpath(path, ROOT))
    print('  действий: %d · упоминаний: %d' % (len(actor), len(mention)))
    return 0


def main():
    ap = argparse.ArgumentParser(description='Еженедельный дайджест-смотр канона')
    ap.add_argument('--days', type=int, default=7)
    ap.add_argument('--person', help='след участника в журнале (фильтр, не агрегат)')
    a = ap.parse_args()
    if a.person:
        return person_digest(a.person)

    sys.path.insert(0, ROOT)
    from build import load_cards, load_rubrics, health_rows
    cards, rubrics = load_cards(), load_rubrics()

    today = datetime.date.today()
    since = today - datetime.timedelta(days=a.days)
    iso_year, iso_week, _ = today.isocalendar()
    did = '%d-W%02d' % (iso_year, iso_week)

    # --- события журнала за период
    events = []
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding='utf-8'):
            parts = [p.strip() for p in line.split(' | ')]
            if parts and parts[0][:10] >= since.isoformat():
                events.append(parts)

    # --- открытые вопросы (backlog рубрик)
    open_q = []
    if os.path.isdir(QUESTIONS):
        for f in sorted(os.listdir(QUESTIONS)):
            if not f.endswith('.md'):
                continue
            src = open(os.path.join(QUESTIONS, f), encoding='utf-8').read()
            if 'status: open' in src:
                title = re.search(r'title: "(.*)"', src).group(1)
                rubric = re.search(r'rubric: (\S+)', src).group(1)
                created = re.search(r'created_at: (\S+)', src).group(1)
                age = (today - datetime.date.fromisoformat(created)).days
                open_q.append((f[:-3], title, rubric, age))

    # --- сигналы «полезно» за период
    useful = []
    if os.path.exists(USEFUL):
        for line in open(USEFUL, encoding='utf-8'):
            if line[:10] >= since.isoformat():
                useful.append(line.strip())

    # --- зоны здоровья
    zones = health_rows(cards, rubrics)

    out = ['# Дайджест недели %s (%s … %s)' % (did, since.isoformat(), today.isoformat()), '',
           '> Ритуал (документ 13): хранители читают в начале недели, 15 минут.', '']
    out.append('## События журнала (%d)' % len(events))
    out.append('')
    out += ['- `%s` **%s** (%s)' % (e[1], e[3], e[2]) for e in events] or ['- тишина']
    out.append('')
    out.append('## Открытые вопросы — backlog рубрик (%d)' % len(open_q))
    out.append('')
    out += ['- ❓ **%s** «%s» (%s, %d дн.)' % q for q in open_q] or ['- нет — спрос закрыт каноном']
    if any(q[3] > 30 for q in open_q):
        out.append('')
        out.append('⚠️ Есть вопросы старше 30 дней — жёлтая зона спроса (документ 15 §15.2).')
    out.append('')
    out.append('## Сигналы «полезно» за период (%d)' % len(useful))
    out.append('')
    out += ['- 👍 %s' % u.split(' | ')[-1] for u in useful] or ['- нет']
    out.append('')
    out.append('## Зоны здоровья канона')
    out.append('')
    mark = {'green': '🟢', 'yellow': '🟡', 'red': '🔴'}
    out += ['- %s %s — %s' % (mark[z], m, v) for m, v, z in zones]
    out.append('')
    out.append('---')
    out.append('*Собрано digest.py %s. Анти-метрики сознательно не измеряются.*'
               % today.isoformat())

    os.makedirs(DIGEST, exist_ok=True)
    path = os.path.join(DIGEST, did + '.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('Дайджест: %s' % os.path.relpath(path, ROOT))
    print('  событий: %d · open-вопросов: %d · сигналов «полезно»: %d' % (len(events), len(open_q), len(useful)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
