#!/usr/bin/env python3
"""
appeal.py — апелляции авторов на возврат правок (документ 04, §22.8, §18.9.4).

Использование:
  python3 appeal.py status
  python3 appeal.py file ch-0002 --by pavel_d --reason "тезис оформлен как гипотеза, источник добавлен"
  python3 appeal.py verdict ap-0001 --by marina_k --decision reject --comment "возврат по пункту 2 чек-листа корректен"

Правила:
  * апелляция возможна только на заявку в state: returned и только её автором;
  * одна апелляция на одну заявку (апелляция — не инструмент затягивания);
  * арбитр — действующий садовник (документ 18 §18.9.4);
  * МЕХАНИЧЕСКИЙ ОТВОД: арбитром не может быть ни хранитель, вернувший
    заявку, ни её автор (конфликт интересов отсекается кодом, не нормой);
  * вердикт публичен: appeal.upheld / appeal.rejected в журнале, подписано
    ключом арбитра;
  * при удовлетворении (upheld) заявка возвращается в state: open с пометкой
    review_ban: вернувший хранитель больше не может ревьюить эту заявку
    (проверяется в review_change.py) — повторное ревью делает другой человек.
"""
import sys, os, re, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import ROOT, parse_frontmatter
from trust import append_ledger, all_keepers
from election import load_gardeners, current_nicks

APPEALS = os.path.join(ROOT, 'appeals')
CHANGES = os.path.join(ROOT, 'changes')
MIN_REASON_WORDS = 5


def load_change(ch_id):
    p = os.path.join(CHANGES, ch_id + '.md')
    if not os.path.exists(p):
        print(f'ОТКАЗ: заявка {ch_id} не найдена'); sys.exit(1)
    text = open(p, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    return p, parse_frontmatter(m.group(1)), m.group(2), text


def load_appeal(ap_id):
    p = os.path.join(APPEALS, ap_id + '.md')
    if not os.path.exists(p):
        print(f'ОТКАЗ: апелляция {ap_id} не найдена'); sys.exit(1)
    text = open(p, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    return p, parse_frontmatter(m.group(1)), m.group(2), text


def next_ap_id():
    os.makedirs(APPEALS, exist_ok=True)
    n = 0
    for f in os.listdir(APPEALS):
        m = re.match(r'ap-(\d{4})\.md', f)
        if m:
            n = max(n, int(m.group(1)))
    return f'ap-{n+1:04d}'


def appeal_for_change(ch_id):
    """Апелляция на эту заявку уже существует?"""
    if not os.path.isdir(APPEALS):
        return None
    for f in sorted(os.listdir(APPEALS)):
        if not f.endswith('.md'):
            continue
        text = open(os.path.join(APPEALS, f), encoding='utf-8').read()
        if f'change: {ch_id}' in text:
            return f[:-3]
    return None


def actor_for(nick):
    return ('keeper:' if nick in all_keepers() else 'author:') + nick


def cmd_status(_a):
    if not os.path.isdir(APPEALS) or not os.listdir(APPEALS):
        print('апелляций нет')
        return
    for f in sorted(os.listdir(APPEALS)):
        if not f.endswith('.md'):
            continue
        text = open(os.path.join(APPEALS, f), encoding='utf-8').read()
        fm = parse_frontmatter(re.match(r'^---\n(.*?)\n---\n', text, re.S).group(1))
        print(f"{fm.get('id')}  {fm.get('change')}  {fm.get('state')}  "
              f"автор={fm.get('author')}  арбитр={fm.get('arbiter', '—')}")


def cmd_file(a):
    ch_path, meta, body, full = load_change(a.change)
    if meta.get('state') != 'returned':
        print(f"ОТКАЗ: апелляция возможна только на возвращённую заявку "
              f"(state: {meta.get('state')})"); sys.exit(1)
    if a.by != meta.get('author'):
        print(f"ОТКАЗ: апелляцию может подать только автор заявки "
              f"({meta.get('author')}), не {a.by}"); sys.exit(1)
    if len(a.reason.split()) < MIN_REASON_WORDS:
        print(f"ОТКАЗ: причина апелляции — минимум {MIN_REASON_WORDS} слов "
              f"(что изменилось или почему возврат не по чек-листу)"); sys.exit(1)
    dup = appeal_for_change(a.change)
    if dup:
        print(f"ОТКАЗ: апелляция на {a.change} уже существует ({dup}) — "
              f"одна апелляция на одну заявку"); sys.exit(1)

    ap_id = next_ap_id()
    text = f"""---
id: {ap_id}
change: {a.change}
card: {meta.get('card')}
author: {a.by}
returned_by: {meta.get('reviewer')}
state: open
created_at: {__import__('datetime').date.today().isoformat()}
---

## Причина апелляции

{a.reason}

## Вердикт арбитра

(ожидает)
"""
    open(os.path.join(APPEALS, ap_id + '.md'), 'w', encoding='utf-8').write(text)
    lid = append_ledger(actor_for(a.by), 'appeal.filed', appeal=ap_id,
                        change=a.change, reason=a.reason)
    print(f'OK: апелляция {ap_id} на {a.change} подана ({lid}); '
          f'арбитр — любой действующий садовник, кроме {meta.get("reviewer")} и {a.by}')


def cmd_verdict(a):
    ap_path, meta, body, full = load_appeal(a.appeal)
    if meta.get('state') != 'open':
        print(f"ОТКАЗ: апелляция уже решена (state: {meta.get('state')})"); sys.exit(1)
    ch_path, ch_meta, ch_body, ch_full = load_change(meta['change'])

    gardeners, _history = load_gardeners()
    gardeners = current_nicks(gardeners)
    if a.by not in gardeners:
        print(f"ОТКАЗ: арбитром может быть только действующий садовник "
              f"({', '.join(gardeners)}), не {a.by}"); sys.exit(1)
    # Механический отвод (§18.9.4): арбитр не может быть стороной спора.
    if a.by == meta.get('returned_by'):
        print(f"ОТВОД: {a.by} вернул(а) заявку {meta['change']} — "
              f"не может быть арбитром по апелляции на собственное решение"); sys.exit(1)
    if a.by == meta.get('author'):
        print(f"ОТВОД: {a.by} — автор заявки {meta['change']} — "
              f"не может быть арбитром собственной апелляции"); sys.exit(1)
    if len(a.comment.split()) < MIN_REASON_WORDS:
        print(f"ОТКАЗ: комментарий вердикта — минимум {MIN_REASON_WORDS} слов "
              f"(вердикт публичен и читается обеими сторонами)"); sys.exit(1)

    import datetime
    today = datetime.date.today().isoformat()
    new_state = 'upheld' if a.decision == 'uphold' else 'rejected'
    new_full = full.replace('state: open', f'state: {new_state}', 1)
    new_full = new_full.replace(
        '## Вердикт арбитра\n\n(ожидает)',
        f'## Вердикт арбитра\n\nарбитр: {a.by}  \nдата: {today}  \n'
        f'решение: {"апелляция удовлетворена, возврат отменён" if a.decision == "uphold" else "возврат подтверждён"}\n\n{a.comment}')
    new_full = new_full.replace('state: ' + new_state,
                                f'state: {new_state}\narbiter: {a.by}\ndecided_at: {today}', 1)
    open(ap_path, 'w', encoding='utf-8').write(new_full)

    if a.decision == 'uphold':
        # Заявка возвращается в работу; вернувший хранитель отведён от ревью.
        new_ch = ch_full.replace('state: returned',
                                 f'state: open\nreview_ban: {meta.get("returned_by")}', 1)
        open(ch_path, 'w', encoding='utf-8').write(new_ch)
        lid = append_ledger(f'gardener:{a.by}', 'appeal.upheld', appeal=a.appeal,
                            change=meta['change'], comment=a.comment)
        print(f'OK: апелляция {a.appeal} удовлетворена ({lid}); заявка {meta["change"]} '
              f'снова открыта, {meta.get("returned_by")} отведён от её ревью')
    else:
        lid = append_ledger(f'gardener:{a.by}', 'appeal.rejected', appeal=a.appeal,
                            change=meta['change'], comment=a.comment)
        print(f'OK: апелляция {a.appeal} отклонена, возврат подтверждён ({lid})')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    p = sub.add_parser('file')
    p.add_argument('change')
    p.add_argument('--by', required=True, help='автор заявки')
    p.add_argument('--reason', required=True)
    p = sub.add_parser('verdict')
    p.add_argument('appeal')
    p.add_argument('--by', required=True, help='действующий садовник-арбитр')
    p.add_argument('--decision', required=True, choices=['uphold', 'reject'],
                   help='uphold — отменить возврат; reject — подтвердить возврат')
    p.add_argument('--comment', required=True)
    a = ap.parse_args()
    {'status': cmd_status, 'file': cmd_file, 'verdict': cmd_verdict}[a.cmd](a)


if __name__ == '__main__':
    main()
