#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
federate.py — федеративные анонсы карточек (фаза 3, документ 10 §10.5).

Карточка -> ActivityStreams 2.0 Article:
  attributedTo = хранитель (Person), updated = verified_at,
  name = заголовок, content = HTML, source = исходный Markdown,
  tag = рубрики, summary = статус + версия.

Другие инстансы Библиотеки подписываются на outbox рубрик —
как на RSS, но с идентичностью авторов (хранитель — публичная роль).

Zero-dependency: генерируются статические JSON-документы в
dist/federation/ (actors.json, outbox-<rubric>.json, <card>.json).
Живого HTTP-сервера нет — это формат обмена, а не демон.

Использование:
  python3 federate.py            # -> dist/federation/
  python3 federate.py --base https://lib.example.org   # базовый URL инстанса
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, 'dist', 'federation')
BASE = 'https://zh-lib.local'


def actor(keeper, base):
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'type': 'Person',
        'id': '%s/federation/actors/%s' % (base, keeper),
        'preferredUsername': keeper,
        'name': 'Хранитель @%s' % keeper,
        'summary': 'Именная роль в Живой Библиотеке: власть срочная, публичная, обжалуемая.',
    }


def article(card, base):
    m = card
    fr = m.get('freshness', {})
    return {
        '@context': 'https://www.w3.org/ns/activitystreams',
        'type': 'Article',
        'id': '%s/federation/%s' % (base, m['id']),
        'attributedTo': '%s/federation/actors/%s' % (base, m.get('keeper', 'unknown')),
        'name': m.get('title', ''),
        'summary': 'статус: %s · версия %s · проверено %s' % (
            m.get('status', '?'), m.get('version', '1'), fr.get('verified_at', '—')),
        'updated': fr.get('verified_at', ''),
        'content': m.get('body_html', ''),
        'source': {'content': m.get('body_raw', ''), 'mediaType': 'text/markdown'},
        'tag': [{'type': 'Hashtag', 'name': r} for r in m.get('rubrics', [])],
        'zh:status': m.get('status', ''),
        'zh:version': m.get('version', '1'),
        'zh:reviewDue': fr.get('review_due', ''),
    }


def main():
    ap = argparse.ArgumentParser(description='ActivityPub-анонсы карточек')
    ap.add_argument('--base', default=BASE, help='публичный URL инстанса')
    a = ap.parse_args()

    sys.path.insert(0, ROOT)
    from build import load_cards, load_rubrics
    cards, rubrics = load_cards(), load_rubrics()

    os.makedirs(OUT, exist_ok=True)
    keepers = sorted({c.get('keeper') for c in cards if c.get('keeper')})
    json.dump([actor(k, a.base) for k in keepers],
              open(os.path.join(OUT, 'actors.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    n = 0
    for c in cards:
        json.dump(article(c, a.base),
                  open(os.path.join(OUT, c['id'] + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        n += 1

    for r in rubrics:
        rc = [c for c in cards if r['id'] in c.get('rubrics', [])]
        if not rc:
            continue
        outbox = {
            '@context': 'https://www.w3.org/ns/activitystreams',
            'type': 'OrderedCollection',
            'id': '%s/federation/outbox-%s' % (a.base, r['id'].replace('/', '_')),
            'name': 'Рубрика «%s» — анонсы версий' % r.get('title', r['id']),
            'totalItems': len(rc),
            'orderedItems': [
                {'type': 'Announce',
                 'actor': '%s/federation/actors/%s' % (a.base, c.get('keeper', 'unknown')),
                 'object': '%s/federation/%s' % (a.base, c['id']),
                 'published': c.get('freshness', {}).get('verified_at', '')}
                for c in sorted(rc, key=lambda c: c.get('freshness', {}).get('verified_at', ''),
                                reverse=True)],
        }
        json.dump(outbox,
                  open(os.path.join(OUT, 'outbox-%s.json' % r['id'].replace('/', '_')),
                       'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)

    print('Федерация: %d карточек -> Article, %d хранителей -> actors, outbox по рубрикам' % (n, len(keepers)))
    print('Каталог: %s (зеркало подписывается на change.accepted -> pull, лаг — минуты)' % OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
