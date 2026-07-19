#!/usr/bin/env python3
"""
review_change.py — ревью заявки на правку (модель merge/reject, фаза 1).

Использование:
  python3 review_change.py accept ch-0002 --keeper igor_s --comment "принято по чек-листу"
  python3 review_change.py return ch-0002 --keeper igor_s --comment "чего не хватает: ..."

Правила (документы 04 и 11):
  * --comment ОБЯЗАТЕЛЕН и при accept, и при return
    («вернуть без подсказки невозможно» — правило вшито в интерфейс);
  * accept: предлагаемый текст заменяет файл карточки в canon/;
  * любое действие пишется в _ledger.log (публичный журнал власти).
"""
import sys, os, re, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import ROOT, parse_frontmatter

LEDGER = os.path.join(ROOT, '_ledger.log')

def load_change(ch_id):
    p = os.path.join(ROOT, 'changes', ch_id + '.md')
    if not os.path.exists(p):
        raise SystemExit(f"заявка {ch_id} не найдена")
    text = open(p, encoding='utf-8').read()
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    return p, parse_frontmatter(m.group(1)), m.group(2), text

def next_ledger_id():
    nums = [int(m.group(1)) for line in open(LEDGER, encoding='utf-8')
            if (m := re.search(r'ldg-(\d+)', line))]
    return f"ldg-{(max(nums) + 1) if nums else 1:04d}"

def extract_proposed(body):
    m = re.search(r'## proposed\n\n```markdown\n(.*?)\n```', body, re.S)
    if not m:
        raise SystemExit("в заявке нет блока proposed (возможно, она историческая)")
    return m.group(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('action', choices=['accept', 'return'])
    ap.add_argument('change_id')
    ap.add_argument('--keeper', required=True)
    ap.add_argument('--comment', required=True,
                    help='обязателен: причина принятия или подсказка, чего не хватает')
    a = ap.parse_args()
    if not a.comment.strip():
        raise SystemExit("комментарий ревью обязателен (правило интерфейса)")

    ch_path, meta, body, full = load_change(a.change_id)
    if meta.get('state') != 'open':
        raise SystemExit(f"заявка уже закрыта (state: {meta.get('state')})")

    if a.action == 'accept':
        proposed = extract_proposed(body)
        card_path = os.path.join(ROOT, meta['card_path'])
        open(card_path, 'w', encoding='utf-8').write(proposed)
        event = 'change.accepted'
        print(f"OK: {a.change_id} принята, карточка {meta['card']} обновлена")
    else:
        event = 'change.returned'
        print(f"OK: {a.change_id} возвращена автору с подсказкой")

    full = full.replace('state: open', f'state: {"accepted" if a.action=="accept" else "returned"}', 1)
    full = full.replace('reviewer: ""', f'reviewer: {a.keeper}', 1)
    full = full.replace('review_comment: ""', f'review_comment: "{a.comment}"', 1)
    open(ch_path, 'w', encoding='utf-8').write(full)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(f'{ts} | {next_ledger_id()} | keeper:{a.keeper} | {event} | '
                f'change={a.change_id} | card={meta["card"]} | comment="{a.comment}"\n')

if __name__ == '__main__':
    main()
