#!/usr/bin/env python3
"""
Живая Библиотека — публикация черновика в канон (документы 10 §10.4, 15).

Машина черновит, человек публикует. Черновик живёт в inbox/ и не имеет
статуса канона; единственный путь в канон — решение хранителя рубрики:

  python3 publish.py publish kn-2026-0418 --keeper marina_k --comment "проверил, источник уровня C помечен"
  python3 publish.py return  kn-2026-0421 --keeper marina_k --comment "тред мал, дополнить обсуждением"

publish: черновик → canon/<rubric>/ со статусом aktualno, свежей датой
проверки и хранителем; событие draft.published (подписано ключом хранителя,
если есть — sign.py).
return: черновик остаётся в inbox/ с пометкой review_state: returned и
комментарием, что доработать; событие draft.returned. Возврат — не удаление:
работа не теряется (документ 11.4 — комментарий обязателен).
"""
import argparse, datetime, glob, os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(ROOT, 'inbox')
CANON = os.path.join(ROOT, 'canon')
LEDGER = os.path.join(ROOT, '_ledger.log')

sys.path.insert(0, ROOT)
try:
    import sign as _sign
except ImportError:
    _sign = None


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def append_ledger(actor, event, **kv):
    n = 0
    for l in open(LEDGER, encoding='utf-8'):
        m = re.search(r'ldg-(\d+)', l)
        if m:
            n = max(n, int(m.group(1)))
    parts = [now(), f'ldg-{n+1:04d}', actor, event]
    for k, v in kv.items():
        v = str(v)
        parts.append(f'{k}="{v}"' if ' ' in v else f'{k}={v}')
    line = ' | '.join(parts)
    if _sign:
        nick = _sign.actor_nick(actor)
        if nick:
            line = _sign.sign_line(nick, line)
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    return f'ldg-{n+1:04d}'


def find_draft(cid):
    hits = glob.glob(os.path.join(INBOX, cid + '-*.md')) + \
           glob.glob(os.path.join(INBOX, cid + '.md'))
    return hits[0] if hits else None


def get(text, key, default=''):
    m = re.search(r'^' + key + r':\s*(.+)$', text, re.M)
    return m.group(1).strip() if m else default


def cmd_publish(a):
    path = find_draft(a.card)
    if not path:
        print(f'ОТКАЗ: черновика {a.card} нет в inbox/')
        sys.exit(1)
    text = open(path, encoding='utf-8').read()
    if 'status: chernovik' not in text and 'review_state: returned' not in text:
        print('ОТКАЗ: это не черновик (status != chernovik)')
        sys.exit(1)
    rubric = get(text, 'rubrics').strip('[]').split(',')[0].strip()
    if not rubric:
        print('ОТКАЗ: у черновика нет рубрики')
        sys.exit(1)
    today = datetime.date.today()
    due = today + datetime.timedelta(days=180)
    text = re.sub(r'^status:.*$', 'status: aktualno', text, count=1, flags=re.M)
    text = re.sub(r'^  verified_at:.*$', '  verified_at: ' + today.isoformat(),
                  text, count=1, flags=re.M)
    text = re.sub(r'^  review_due:.*$', '  review_due: ' + due.isoformat(),
                  text, count=1, flags=re.M)
    text = re.sub(r'^keeper:.*$', 'keeper: ' + a.keeper, text, count=1, flags=re.M)
    text = re.sub(r'^review_state:.*\n', '', text, count=1, flags=re.M)
    text = re.sub(r'^review_comment:.*\n', '', text, count=1, flags=re.M)
    text = text.replace(
        '> Черновик, дистиллированный машиной',
        '> Опубликовано хранителем @%s %s. Исходный черновик дистиллирован машиной'
        % (a.keeper, today.isoformat()), 1)
    dest_dir = os.path.join(CANON, rubric)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, a.card + '.md')
    open(dest, 'w', encoding='utf-8').write(text)
    os.remove(path)
    lid = append_ledger(f'keeper:{a.keeper}', 'draft.published',
                        card=a.card, rubric=rubric, comment=a.comment)
    print(f'{a.card} опубликована в canon/{rubric}/ ({lid}); '
          f'статус aktualno, проверено {today.isoformat()}, ревизия до {due.isoformat()}')


def cmd_return(a):
    path = find_draft(a.card)
    if not path:
        print(f'ОТКАЗ: черновика {a.card} нет в inbox/')
        sys.exit(1)
    text = open(path, encoding='utf-8').read()
    text = text.replace('status: chernovik',
                        'status: chernovik\nreview_state: returned\nreview_comment: "%s"' % a.comment, 1)
    open(path, 'w', encoding='utf-8').write(text)
    lid = append_ledger(f'keeper:{a.keeper}', 'draft.returned',
                        card=a.card, comment=a.comment)
    print(f'{a.card} возвращён на доработку ({lid}); черновик сохранён в inbox/, '
          f'комментарий — в файле и журнале (§11.4)')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('publish')
    p.add_argument('card'); p.add_argument('--keeper', required=True)
    p.add_argument('--comment', required=True)
    p.set_defaults(f=cmd_publish)
    p = sub.add_parser('return')
    p.add_argument('card'); p.add_argument('--keeper', required=True)
    p.add_argument('--comment', required=True)
    p.set_defaults(f=cmd_return)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
