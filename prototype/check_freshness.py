#!/usr/bin/env python3
"""
check_freshness.py — сканер здоровья канона (документ 13, фаза 1).

Использование:
  python3 check_freshness.py           # отчёт в консоль; exit 1, если есть красные зоны
  python3 check_freshness.py --links   # + проверка живости внешних источников (HEAD)

Проверки (подмножество панели здоровья):
  * % карточек со свежей ревизией (review_due >= сегодня);
  * сиротские карточки (нет keeper);
  * хранителей на рубрику (<2 — жёлтая зона, 0 — красная);
  * опционально: мёртвые внешние ссылки уровня S/A/B (link rot).
"""
import sys, os, datetime, urllib.request, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import load_cards, load_rubrics

def zone(ok, warn):
    return 'GREEN' if ok else ('YELLOW' if warn else 'RED')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--links', action='store_true')
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
        z = zone(len(keepers) >= 2, len(keepers) == 1)
        red |= z == 'RED'
        print(f"[{z:6}] рубрика {r['id']}: хранителей {len(keepers)}")

    stale = [c['id'] for c in cards
             if c.get('freshness', {}).get('review_due', '9999') < today.isoformat()]
    if stale:
        print(f"       ⚠ просрочены ревизии: {stale}")

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

    print("\nИТОГ:", "КРАСНЫЕ ЗОНЫ ЕСТЬ" if red else "все зоны зелёные/жёлтые")
    sys.exit(1 if red else 0)

if __name__ == '__main__':
    main()
