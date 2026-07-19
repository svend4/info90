#!/usr/bin/env python3
"""
propose_change.py — предложить правку карточки (модель Pull Request, фаза 1).

Использование:
  python3 propose_change.py <card_id> <edited_file.md> "<причина правки>" --author <ник>

Скрипт:
  1. находит карточку в canon/ по id;
  2. автоматически поднимает version и обновляет freshness.verified_at
     в предлагаемом файле (если автор не сделал это сам);
  3. считает unified diff;
  4. пишет заявку changes/ch-NNNN.md (state: open);
  5. добавляет запись change.proposed в _ledger.log.

Причина правки обязательна (документ 11: «описание правки» доведено до обязательности).
"""
import sys, os, re, difflib, datetime, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import CANON, ROOT, split_card, parse_frontmatter

LEDGER = os.path.join(ROOT, '_ledger.log')
CHANGES = os.path.join(ROOT, 'changes')

def find_card_path(card_id):
    for dirpath, _, files in os.walk(CANON):
        for f in files:
            if f.endswith('.md'):
                p = os.path.join(dirpath, f)
                text = open(p, encoding='utf-8').read()
                meta, _ = split_card(text)
                if meta.get('id') == card_id:
                    return p, text
    raise SystemExit(f"карточка {card_id} не найдена")

def next_change_id():
    os.makedirs(CHANGES, exist_ok=True)
    nums = [int(m.group(1)) for f in os.listdir(CHANGES)
            if (m := re.match(r'ch-(\d+)\.md', f))]
    return f"ch-{(max(nums) + 1) if nums else 1:04d}"

def next_ledger_id():
    if not os.path.exists(LEDGER):
        return 'ldg-0001'
    nums = [int(m.group(1)) for line in open(LEDGER, encoding='utf-8')
            if (m := re.search(r'ldg-(\d+)', line))]
    return f"ldg-{(max(nums) + 1) if nums else 1:04d}"

def bump_version_and_date(proposed_text):
    meta, _ = split_card(proposed_text)
    today = datetime.date.today().isoformat()
    fm_lines = proposed_text.split('---')[1].strip().split('\n')
    body_part = proposed_text.split('---', 2)[2]  # сохраняем пустую строку после ---
    out, bumped = [], False
    for line in fm_lines:
        if line.startswith('version:'):
            line = f'version: {int(meta.get("version", 1)) + 1}'
            bumped = True
        elif line.strip().startswith('verified_at:'):
            line = f'  verified_at: {today}'
        out.append(line)
    if not bumped:
        out.append('version: 2')
    return '---\n' + '\n'.join(out) + '\n---' + body_part

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('card_id')
    ap.add_argument('edited_file')
    ap.add_argument('reason')
    ap.add_argument('--author', required=True)
    a = ap.parse_args()
    if not a.reason.strip():
        raise SystemExit("причина правки обязательна")

    card_path, canon_text = find_card_path(a.card_id)
    proposed = open(a.edited_file, encoding='utf-8').read()
    proposed = bump_version_and_date(proposed)

    diff = ''.join(difflib.unified_diff(
        canon_text.splitlines(True), proposed.splitlines(True),
        fromfile=f'canon ({a.card_id})', tofile='proposed', n=2))

    ch_id = next_change_id()
    rel = os.path.relpath(card_path, ROOT)
    ch = f"""---
id: {ch_id}
card: {a.card_id}
card_path: {rel}
author: {a.author}
state: open
reason: "{a.reason}"
created_at: {datetime.date.today().isoformat()}
reviewer: ""
review_comment: ""
---

## diff

```diff
{diff}
```

## proposed

```markdown
{proposed}
```
"""
    open(os.path.join(CHANGES, ch_id + '.md'), 'w', encoding='utf-8').write(ch)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(f'{ts} | {next_ledger_id()} | author:{a.author} | change.proposed | '
                f'change={ch_id} | card={a.card_id} | reason="{a.reason}"\n')
    print(f"OK: заявка {ch_id} создана (state: open), журнал пополнен")

if __name__ == '__main__':
    main()
