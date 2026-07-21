#!/usr/bin/env python3
"""
Живая Библиотека — перевыборы садовников (документ 20 §20.3).

Садовник — верховная локальная власть, и потому единственная роль,
которая целиком переизбирается раз в год, при всех. Скрипт проводит
процедуру и фиксирует факты в журнале; он не «считает популярность».

Правила (§20.3):
  * голосуют действующие хранители рубрик и действующие садовники;
  * кворум — строгое большинство от их числа;
  * кандидат на новый срок обязан опубликовать отчёт (--report);
  * не более ДВУХ сроков подряд, затем перерыв >= 1 года;
  * садовников всегда >= 2 (иначе выборы не закрываются);
  * непереизбрание — не recall: gardener.retired с благодарностью.

Команды:
  status
      Реестр: кто садовник, какой срок подряд, до когда; кто в истории.
  nominate <ник> --report <файл.md> [--by X]
      Выдвижение кандидатуры. Отчёт/заявление обязательны — «нет отчёта,
      нет власти». Кандидат — действующий хранитель или садовник.
  elect --candidates a,b --quorum v1,v2,v3
      Закрытие выборов: gardener.elected избранным (срок +1),
      gardener.retired ушедшим по сроку. Номинации из elections/cand-NNNN.md.
  retire <ник> --reason "..." [--by X]
      Добровольный выход до срока: gardener.retired, запись в историю.

Записи выборов — файлы elections/cand-NNNN.md; факты власти — _ledger.log.
"""
import argparse, datetime, os, re, sys

from trust import append_ledger, ledger_lines, all_keepers, TODAY

ROOT = os.path.dirname(os.path.abspath(__file__))
GARDENERS = os.path.join(ROOT, '_gardeners.yml')
ELECTIONS = os.path.join(ROOT, 'elections')
MAX_TERMS = 2          # сроков подряд (§20.3)
BREAK_DAYS = 365       # перерыв после двух сроков
MIN_GARDENERS = 2


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


# ---------- реестр _gardeners.yml (строчный формат, без pyyaml) ----------

def load_gardeners():
    """Возвращает (gardeners, history): списки dict с полями реестра."""
    gardeners, history, section, cur = [], [], None, None
    for line in open(GARDENERS, encoding='utf-8'):
        if line.startswith('gardeners:'):
            section, cur = 'g', None
            continue
        if line.startswith('history:'):
            if cur:
                (gardeners if section == 'g' else history).append(cur)
            section, cur = 'h', None
            continue
        if section is None or line.startswith('#') or not line.strip():
            continue
        m = re.match(r'\s*- nick: (\S+)', line)
        if m:
            if cur:
                (gardeners if section == 'g' else history).append(cur)
            cur = {'nick': m.group(1)}
            continue
        m = re.match(r'\s+(\w+): (.+)', line)
        if m and cur is not None:
            v = re.sub(r'\s+#.*$', '', m.group(2))   # inline-комментарий — не значение
            cur[m.group(1)] = v.strip().strip('"')
    if cur:
        (gardeners if section == 'g' else history).append(cur)
    return gardeners, history


def save_gardeners(gardeners, history):
    out = ["# Реестр садовников (документ 20 §20.3): верховная локальная власть инстанса.",
           "# Правила: садовников всегда >= 2; срок 1 год; не более двух сроков подряд,",
           "# затем обязательный перерыв >= 1 года (потом можно избираться снова).",
           "# Меняется только через election.py — каждая смена пишется в журнал власти.",
           "gardeners:"]
    for g in gardeners:
        out += [f"  - nick: {g['nick']}",
                f"    terms: {g['terms']}",
                f"    since: {g['since']}",
                f"    term_ends: {g['term_ends']}"]
    out.append('history:' if history else 'history: []')
    for h in history:
        out += [f"  - nick: {h['nick']}",
                f"    terms: {h['terms']}",
                f"    retired_at: {h['retired_at']}",
                f'    note: "{h.get("note", "")}"']
    open(GARDENERS, 'w', encoding='utf-8').write('\n'.join(out) + '\n')


def current_nicks(gardeners):
    return [g['nick'] for g in gardeners]


# ---------- номинации ----------

def _nominations():
    if not os.path.isdir(ELECTIONS):
        return {}
    out = {}
    for f in sorted(os.listdir(ELECTIONS)):
        m = re.match(r'(cand-\d{4})\.md', f)
        if m:
            t = open(os.path.join(ELECTIONS, f), encoding='utf-8').read()
            st = re.search(r'^state: (\w+)', t, re.M)
            cand = re.search(r'^candidate: (\S+)', t, re.M)
            if st and cand:
                out.setdefault(cand.group(1), []).append((m.group(1), st.group(1)))
    return out


def _check_term_limit(nick, gardeners, history):
    """True, если ник может быть избран (лимит сроков не исчерпан)."""
    for g in gardeners:
        if g['nick'] == nick:
            if int(g['terms']) >= MAX_TERMS:
                return False, (f'{nick} отслужил {MAX_TERMS} срока подряд — '
                               f'обязателен перерыв >= 1 года (§20.3)')
            return True, ''
    for h in history:
        if h['nick'] == nick and int(h.get('terms', 0)) >= MAX_TERMS:
            try:
                d = datetime.date.fromisoformat(h['retired_at'][:10])
                left = BREAK_DAYS - (TODAY - d).days
            except (KeyError, ValueError):
                left = 0
            if left > 0:
                return False, (f'{nick} ушёл после {MAX_TERMS} сроков подряд; '
                               f'перерыв ещё {left} дн. (§20.3)')
    return True, ''


# ---------- команды ----------

def cmd_status(a):
    gardeners, history = load_gardeners()
    noms = _nominations()
    print(f'Садовники ({len(gardeners)}, минимум {MIN_GARDENERS}):')
    for g in gardeners:
        left = (datetime.date.fromisoformat(g['term_ends']) - TODAY).days
        print(f"  {g['nick']:12s} срок {g['terms']}/{MAX_TERMS} подряд · полномочия до {g['term_ends']} ({left} дн.)")
    if history:
        print('История:')
        for h in history:
            print(f"  {h['nick']:12s} сроков: {h['terms']} · вышел {h['retired_at']} · {h.get('note','')}")
    active = [(c, i) for c, ids in noms.items() for i, s in ids if s == 'nominated']
    if active:
        print('Номинированы:', ', '.join(f'{c} ({i})' for c, i in active))
    elig = sorted(set(all_keepers()) | set(current_nicks(gardeners)))
    print(f'Электорат (хранители ∪ садовники): {len(elig)} чел.; кворум > {len(elig)//2}')


def cmd_nominate(a):
    gardeners, history = load_gardeners()
    elig_persons = set(all_keepers()) | set(current_nicks(gardeners))
    if a.nick not in elig_persons:
        print(f'ОТКАЗ: {a.nick} не действующий хранитель и не садовник — '
              f'садовником может стать тот, кто уже читал историю власти (§20.3)')
        sys.exit(1)
    ok, why = _check_term_limit(a.nick, gardeners, history)
    if not ok:
        print(f'ОТКАЗ: {why}')
        sys.exit(1)
    if not os.path.exists(a.report):
        print(f'ОТКАЗ: нет файла отчёта {a.report} — «нет отчёта, нет власти» (§20.3)')
        sys.exit(1)
    report = open(a.report, encoding='utf-8').read()
    if len(report.split()) < 20:
        print('ОТКАЗ: отчёт формальный (меньше 20 слов) — опишите срок: решения, красные зоны, итоги')
        sys.exit(1)
    for cid, st in _nominations().get(a.nick, []):
        if st == 'nominated':
            print(f'ОТКАЗ: {a.nick} уже номинирован ({cid})')
            sys.exit(1)
    os.makedirs(ELECTIONS, exist_ok=True)
    n = 0
    for f in os.listdir(ELECTIONS):
        m = re.match(r'cand-(\d{4})\.md', f)
        if m:
            n = max(n, int(m.group(1)))
    cid = f'cand-{n+1:04d}'
    open(os.path.join(ELECTIONS, cid + '.md'), 'w', encoding='utf-8').write(f"""---
id: {cid}
state: nominated
candidate: {a.nick}
nominated_by: {a.by}
created_at: {now()}
---

## Отчёт / заявление кандидата

{report}
""")
    print(f'{cid}: {a.nick} выдвинут садовником (отчёт принят, {len(report.split())} слов); '
          f'14 дней обсуждения — вопросы по фактам журнала, затем elect')


def cmd_elect(a):
    gardeners, history = load_gardeners()
    cur = current_nicks(gardeners)
    candidates = [c.strip() for c in a.candidates.split(',') if c.strip()]
    quorum = [q.strip() for q in a.quorum.split(',') if q.strip()]
    electorate = sorted(set(all_keepers()) | set(cur))
    bad = [q for q in quorum if q not in electorate]
    if bad:
        print(f'ОТКАЗ: {", ".join(bad)} не из электората (хранители ∪ садовники)')
        sys.exit(1)
    if len(quorum) <= len(electorate) // 2:
        print(f'ОТКАЗ: кворум {len(quorum)} из {len(electorate)} — нужно строгое большинство '
              f'действующих хранителей и садовников (§20.3)')
        sys.exit(1)
    noms = _nominations()
    for c in candidates:
        if not any(st == 'nominated' for _, st in noms.get(c, [])):
            print(f'ОТКАЗ: {c} не номинирован (нет активной cand-записи с отчётом)')
            sys.exit(1)
        ok, why = _check_term_limit(c, gardeners, history)
        if not ok:
            print(f'ОТКАЗ: {why}')
            sys.exit(1)
    outgoing = [g for g in gardeners if g['nick'] not in candidates]
    incoming_new = [c for c in candidates if c not in cur]
    if len(cur) - len(outgoing) + len(incoming_new) < MIN_GARDENERS:
        print(f'ОТКАЗ: итог выборов оставит инстанс с менее чем {MIN_GARDENERS} садовниками — '
              f'сначала добавьте кандидата (правило ≥2, §20.9.2)')
        sys.exit(1)

    gardeners = [g for g in gardeners if g['nick'] in candidates]  # ушедшие — только в history
    year_end = datetime.date(TODAY.year + 1, TODAY.month, TODAY.day).isoformat()
    qs = ','.join(quorum)
    for c in candidates:
        if c in cur:
            g = next(g for g in gardeners if g['nick'] == c)
            g['terms'] = str(int(g['terms']) + 1)
            g['since'] = TODAY.isoformat()
            g['term_ends'] = year_end
        else:
            gardeners.append({'nick': c, 'terms': '1',
                              'since': TODAY.isoformat(), 'term_ends': year_end})
        lid = append_ledger('gardener:system', 'gardener.elected',
                            gardener=c, terms=next(g['terms'] for g in gardeners if g['nick'] == c),
                            quorum=qs, until=year_end,
                            comment=f'избран на дне сада; срок до {year_end} (§20.3)')
        print(f'  ✓ {c} — gardener.elected ({lid})')
    for g in outgoing:
        history.append({'nick': g['nick'], 'terms': g['terms'],
                        'retired_at': now(),
                        'note': 'выход по сроку: не переизбран; норма, не recall'})
        lid = append_ledger('gardener:system', 'gardener.retired',
                            gardener=g['nick'], quorum=qs,
                            comment=f'срок завершён с благодарностью; история остаётся его историей (§20.3)')
        print(f'  ↓ {g["nick"]} — gardener.retired ({lid})')
    # отметить номинации
    for c in candidates + [g['nick'] for g in outgoing]:
        for cid, st in noms.get(c, []):
            if st == 'nominated':
                p = os.path.join(ELECTIONS, cid + '.md')
                t = open(p, encoding='utf-8').read()
                new_st = 'elected' if c in candidates else 'closed'
                open(p, 'w', encoding='utf-8').write(t.replace('state: nominated', f'state: {new_st}', 1))
    save_gardeners(gardeners, history)
    print(f'Выборы закрыты: садовники — {", ".join(current_nicks(gardeners))}; кворум {len(quorum)}/{len(electorate)}')


def cmd_retire(a):
    gardeners, history = load_gardeners()
    if a.nick not in current_nicks(gardeners):
        print(f'ОТКАЗ: {a.nick} не садовник')
        sys.exit(1)
    if len(gardeners) - 1 < MIN_GARDENERS:
        print(f'ОТКАЗ: выход оставит инстанс с менее чем {MIN_GARDENERS} садовниками — '
              f'сначала досрочные выборы (§20.9.2)')
        sys.exit(1)
    g = next(g for g in gardeners if g['nick'] == a.nick)
    gardeners = [x for x in gardeners if x['nick'] != a.nick]
    history.append({'nick': a.nick, 'terms': g['terms'], 'retired_at': now(), 'note': a.reason})
    lid = append_ledger('gardener:system', 'gardener.retired',
                        gardener=a.nick, comment=a.reason)
    save_gardeners(gardeners, history)
    print(f'{a.nick} вышел из садовников ({lid}); запись в истории с благодарностью')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('status'); p.set_defaults(f=cmd_status)
    p = sub.add_parser('nominate')
    p.add_argument('nick'); p.add_argument('--report', required=True)
    p.add_argument('--by', default='gardener:system')
    p.set_defaults(f=cmd_nominate)
    p = sub.add_parser('elect')
    p.add_argument('--candidates', required=True); p.add_argument('--quorum', required=True)
    p.set_defaults(f=cmd_elect)
    p = sub.add_parser('retire')
    p.add_argument('nick'); p.add_argument('--reason', required=True)
    p.add_argument('--by', default='gardener:system')
    p.set_defaults(f=cmd_retire)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
