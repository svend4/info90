#!/usr/bin/env python3
"""
check_freshness.py — сканер здоровья канона (документ 13, фаза 1).

Использование:
  python3 check_freshness.py           # отчёт в консоль; exit 1, если есть красные зоны
  python3 check_freshness.py --links   # + проверка живости внешних источников (HEAD)
  python3 check_freshness.py --create-requests  # + заявки хранителям (changes/rq-NNNN.md)

Проверки (подмножество панели здоровья):
  * % карточек со свежей ревизией (review_due >= сегодня);
  * сиротские карточки (нет keeper);
  * хранителей на рубрику (<2 — жёлтая зона, 0 — красная);
  * опционально: мёртвые внешние ссылки уровня S/A/B (link rot).

Правило сканера (документ 10 §10.4): только заявки хранителям,
НИКОГДА — автоправки канона.
"""
import sys, os, re, datetime, urllib.request, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import ROOT, load_cards, load_rubrics

CHANGES = os.path.join(ROOT, 'changes')
LEDGER = os.path.join(ROOT, '_ledger.log')

def zone(ok, warn):
    return 'GREEN' if ok else ('YELLOW' if warn else 'RED')

def next_id(prefix, pattern, path_is_dir):
    best = 0
    if os.path.exists(path_is_dir):
        if os.path.isdir(path_is_dir):
            for f in os.listdir(path_is_dir):
                m = re.match(pattern, f)
                if m:
                    best = max(best, int(m.group(1)))
        else:
            for line in open(path_is_dir, encoding='utf-8'):
                m = re.search(pattern, line)
                if m:
                    best = max(best, int(m.group(1)))
    return '%s-%04d' % (prefix, best + 1)

def create_review_requests(stale_cards, orphan_cards):
    """Заявки хранителям: один файл changes/rq-NNNN.md на прогон. Не правит канон."""
    if not stale_cards and not orphan_cards:
        return None
    os.makedirs(CHANGES, exist_ok=True)
    rid = next_id('rq', r'rq-(\d+)\.md$', CHANGES)
    today = datetime.date.today().isoformat()
    lines = ['# Заявки сканера устаревания %s' % today, '',
             '> Создано автоматически (`check_freshness.py --create-requests`).',
             '> Сканер только просит — правит канон человек-хранитель.', '']
    for c in stale_cards:
        lines.append('- [ ] **%s** «%s» — ревизия просрочена (due: %s). Хранитель: %s.'
                     % (c['id'], c.get('title', ''), c.get('freshness', {}).get('review_due', '?'),
                        c.get('keeper') or 'НЕТ — сирота'))
    for c in orphan_cards:
        lines.append('- [ ] **%s** «%s» — нет хранителя, рубрике нужен доброволец.'
                     % (c['id'], c.get('title', '')))
    path = os.path.join(CHANGES, rid + '.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lid = next_id('ldg', r'ldg-(\d+)', LEDGER)
    open(LEDGER, 'a', encoding='utf-8').write(
        '%s | %s | check_freshness.py | review.requested | request=%s | stale=%d | orphans=%d | '
        'comment="заявки хранителям, автоправок нет"\n'
        % (ts, lid, rid, len(stale_cards), len(orphan_cards)))
    return rid

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--links', action='store_true')
    ap.add_argument('--create-requests', action='store_true',
                    help='создать заявки хранителям changes/rq-NNNN.md (без автоправок)')
    a = ap.parse_args()

    cards, rubrics = load_cards(), load_rubrics()
    today = datetime.date.today()
    red = False

    fresh = [c for c in cards
             if c.get('freshness', {}).get('review_due', '0000-00-00') >= today.isoformat()]
    pct = round(100 * len(fresh) / max(len(cards), 1))
    z = zone(pct > 90, pct >= 75)
    red |= z == 'RED'
    print(f"[{z:6}] свежие ревизии: {pct}% ({len(fresh)}/{len(cards)})")

    orphans = [c['id'] for c in cards if not c.get('keeper')]
    z = zone(not orphans, len(orphans) <= 3)
    red |= z == 'RED'
    print(f"[{z:6}] сиротские карточки: {len(orphans)} {orphans or ''}")

    for r in rubrics:
        if r.get('children'):
            continue
        keepers = {c.get('keeper') for c in cards if r['id'] in c.get('rubrics', [])}
        keepers.discard(None)
        if r.get('keeper'):
            keepers.add(r['keeper'])
        keepers.update(r.get('keepers', []))
        z = zone(len(keepers) >= 2, len(keepers) == 1)
        red |= z == 'RED'
        print(f"[{z:6}] рубрика {r['id']}: хранителей {len(keepers)}")

    stale_cards = [c for c in cards
                   if c.get('freshness', {}).get('review_due', '9999') < today.isoformat()]
    if stale_cards:
        print(f"       ⚠ просрочены ревизии: {[c['id'] for c in stale_cards]}")

    if a.links:
        for c in cards:
            for s in c.get('sources', []):
                url = s.get('url', '')
                if not url.startswith('http'):
                    continue
                try:
                    req = urllib.request.Request(url, method='HEAD',
                                                 headers={'User-Agent': 'zh-lib/0.1'})
                    code = urllib.request.urlopen(req, timeout=5).status
                    st = 'GREEN' if code < 400 else 'RED'
                except Exception as e:
                    st, code = 'RED', type(e).__name__
                red |= st == 'RED'
                print(f"[{st:6}] {c['id']}: {url} -> {code}")

    if a.create_requests:
        orphan_cards = [c for c in cards if not c.get('keeper')]
        rid = create_review_requests(stale_cards, orphan_cards)
        if rid:
            print(f"       → заявки хранителям: changes/{rid}.md (записано в журнал)")

    print("\nИТОГ:", "КРАСНЫЕ ЗОНЫ ЕСТЬ" if red else "все зоны зелёные/жёлтые")
    sys.exit(1 if red else 0)

if __name__ == '__main__':
    main()
