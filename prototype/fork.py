#!/usr/bin/env python3
"""
fork.py — форк рубрики из реплики в собственный канон (документ 17 §«Форки»,
документ 25 §25.4).

Подписка (subscribe.py) даёт чужое знание дома в read-only; форк — это
«забрать рубрику себе»: карточки реплики становятся ЛОКАЛЬНЫМИ карточками
канона с сохранением происхождения.

Правила протокола:
  * источник форка — только реплики <target>/replicas/<instance>/ (нельзя
    форкнуть то, на что не подписан: сначала подписка, потом решение);
  * происхождение сохраняется в паспорте: forked_from {instance, card,
    version, url} + forked_at — форк не скрывает, откуда знание;
  * локальная версия начинается с 1: свежесть теперь забота локального
    хранителя (реплика больше не обновляет форкнутую карточку);
  * конфликт id: если локальный канон уже содержит такой id — отказ
    (сначала разрулить конфликт людьми, протокол не выбирает);
  * реплики остаются на месте: история подписки не стирается;
  * форк — действие власти: подписан ключом локального хранителя рубрики
    (rubric.forked в журнале инстанса, edsig=).

У каждого инстанса — свои ключи (роль@инстанс): keygen создаёт
Ed25519-ключ в <target>/_keys/.

Запуск:
  python3 fork.py keygen daria_v --target /path/to/instance
  python3 fork.py fork formy/katalogi --from lib-alpha --by daria_v \
      --target /path/to/instance --reason "забираем каталоги: сосед замер"
"""
import argparse, datetime, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ed25519


def T(target, *parts):
    return os.path.join(target, *parts)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def today():
    return datetime.date.today().isoformat()


# ---------- ключи инстанса (роль@инстанс) ----------

def cmd_keygen(a):
    keys = T(a.target, '_keys')
    os.makedirs(keys, exist_ok=True)
    p = T(a.target, '_keys', a.nick + '.ed25519')
    if os.path.exists(p):
        print(f'ОТКАЗ: ключ {a.nick} уже существует'); sys.exit(1)
    import secrets
    seed = secrets.token_bytes(32)
    pk = ed25519.publickey(seed)
    open(p, 'w', encoding='utf-8').write(seed.hex() + '\n')
    os.chmod(p, 0o600)
    inst = os.path.basename(os.path.abspath(a.target))
    with open(T(a.target, '_keys', 'registry.yml'), 'a', encoding='utf-8') as f:
        f.write(f'- nick: {a.nick}\n  instance: {inst}\n  ed25519: {pk.hex()}\n  created_at: {utcnow()}\n')
    print(f'Ключ {a.nick}@{inst} создан (приватный — не коммитить); публичный в _keys/registry.yml')


def load_seed(target, nick):
    p = T(target, '_keys', nick + '.ed25519')
    if not os.path.exists(p):
        return None
    return bytes.fromhex(open(p, encoding='utf-8').read().strip())


def append_ledger(target, actor, event, nick=None, **fields):
    ledger = T(target, '_ledger.log')
    n = 1
    if os.path.exists(ledger):
        for l in open(ledger, encoding='utf-8'):
            m = re.search(r'ldg-(\d+)', l)
            if m:
                n = max(n, int(m.group(1)) + 1)
    parts = ' | '.join(f'{k}={v}' for k, v in fields.items())
    line = f'{utcnow()} | ldg-{n:04d} | {actor} | {event} | {parts}'
    if nick:
        seed = load_seed(target, nick)
        if seed:
            pk = ed25519.publickey(seed)
            line += ' | edsig=' + ed25519.signature(line.encode('utf-8'), seed, pk).hex()
    with open(ledger, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    return f'ldg-{n:04d}'


# ---------- форк ----------

def parse_head(text):
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    if not m:
        return {}, text
    head = {}
    for line in m.group(1).splitlines():
        mm = re.match(r'^(\w+):\s*(.*)$', line)
        if mm:
            head[mm.group(1)] = mm.group(2).strip().strip('"')
    return head, m.group(2)


def rubric_keepers(target, rubric):
    """Хранители рубрики из _rubrics.yml инстанса (строковый разбор)."""
    p = T(target, '_rubrics.yml')
    if not os.path.exists(p):
        return []
    keepers = []
    cur = None
    for line in open(p, encoding='utf-8'):
        m = re.match(r'^\s+- id: (\S+)', line)
        if m:
            cur = m.group(1)
        m = re.match(r'^\s+keepers: \[(.*)\]', line)
        if m and cur == rubric:
            keepers = [k.strip() for k in m.group(1).split(',') if k.strip()]
    return keepers


def cmd_fork(a):
    rep_dir = T(a.target, 'replicas', getattr(a, 'from'))
    if not os.path.isdir(rep_dir):
        print(f'ОТКАЗ: нет реплик инстанса {getattr(a, "from")} — '
              f'сначала подписка (subscribe.py), потом форк'); sys.exit(1)

    # карточки реплики нужной рубрики
    cards = []
    for f in sorted(os.listdir(rep_dir)):
        if not f.endswith('.md'):
            continue
        text = open(os.path.join(rep_dir, f), encoding='utf-8').read()
        head, body = parse_head(text)
        rubrics = head.get('rubrics', '')
        if a.rubric in rubrics:
            cards.append((f, head, body))
    if not cards:
        print(f'ОТКАЗ: в репликах {getattr(a, "from")} нет карточек рубрики {a.rubric}'); sys.exit(1)

    keepers = rubric_keepers(a.target, a.rubric)
    if keepers and a.by not in keepers:
        print(f'ОТКАЗ: форк рубрики подписывает её локальный хранитель '
              f'({", ".join(keepers)}), не {a.by}'); sys.exit(1)
    if not load_seed(a.target, a.by):
        print(f'ОТКАЗ: у {a.by} нет ключа этого инстанса — сначала fork.py keygen'); sys.exit(1)
    if len(a.reason.split()) < 5:
        print('ОТКАЗ: причина форка — минимум 5 слов (форк читается и соседом)'); sys.exit(1)

    canon_dir = T(a.target, 'canon', a.rubric)
    os.makedirs(canon_dir, exist_ok=True)
    inst = os.path.basename(os.path.abspath(a.target))
    forked_ids = []
    for fname, head, body in cards:
        cid = head.get('id', fname[:-3])
        if os.path.exists(os.path.join(canon_dir, fname)) or \
           any(cid in open(os.path.join(dp, f), encoding='utf-8').read()
               for dp, _, fs in os.walk(T(a.target, 'canon'))
               for f in fs if f.endswith('.md')):
            print(f'ОТКАЗ: id {cid} уже есть в локальном каноне — '
                  f'конфликт решают люди, протокол не выбирает (§17)'); sys.exit(1)
        # Баннер реплики («read-only, правки не вносятся») в канон не переезжает:
        # форкнутая карточка — локальная, её правки ревьюятся здесь.
        blines = body.lstrip().splitlines()
        while blines and blines[0].startswith('>'):
            blines.pop(0)
        body = '\n'.join(blines).lstrip('\n')
        origin_url = f'https://{getattr(a, "from")}.example.org/federation/{cid}'
        new_text = f"""---
id: {cid}
title: {head.get('title', '').strip(chr(34))}
status: aktualno
version: 1
freshness:
  verified_at: {today()}
  review_due: {datetime.date.today().replace(year=datetime.date.today().year + 1).isoformat()}
keeper: {a.by}
rubrics: [{a.rubric}]
forked_from: {{instance: {getattr(a, 'from')}, card: {cid}, version: {head.get('origin_version', '?')}, url: {origin_url}}}
forked_at: {today()}
---

> **Форк** карточки `{cid}` инстанса `{getattr(a, 'from')}` (документ 17).
> Происхождение — в паспорте (forked_from); версия оригинала на момент
> форка: {head.get('origin_version', '?')}. Дальнейшая свежесть — забота
> локального хранителя (@{a.by}@{inst}); оригинал живёт своей жизнью,
> удаление оригинала на эту копию не распространяется.

""" + body.lstrip()
        open(os.path.join(canon_dir, fname), 'w', encoding='utf-8').write(new_text)
        forked_ids.append(cid)

    # Если рубрики ещё нет в локальном дереве — добавляем с пометкой о форке;
    # форкер становится её первым хранителем.
    if not keepers:
        with open(T(a.target, '_rubrics.yml'), 'a', encoding='utf-8') as f:
            top = a.rubric.split('/')[0]
            f.write(f'  - id: {top}\n'
                    f'    title: "Форк из {getattr(a, "from")}"\n'
                    f'    keepers: [{a.by}]\n'
                    f'    children:\n'
                    f'      - id: {a.rubric}\n'
                    f'        title: "{a.rubric} (форк из {getattr(a, "from")})"\n'
                    f'        keepers: [{a.by}]\n')
        print(f'Рубрика {a.rubric} добавлена в _rubrics.yml (хранитель: {a.by})')

    lid = append_ledger(a.target, f'keeper:{a.by}', 'rubric.forked',
                        nick=a.by, rubric=a.rubric,
                        **{'from': getattr(a, 'from'),
                           'cards': ','.join(forked_ids),
                           'comment': f'"{a.reason}"'})
    print(f'OK: рубрика {a.rubric} форкнута из {getattr(a, "from")} ({lid}, подписано):')
    for cid in forked_ids:
        print(f'  {cid} → canon/{a.rubric}/ (локальная версия 1, происхождение в паспорте)')
    print('Реплики не тронуты: история подписки остаётся; обновления оригинала '
          'на форкнутые карточки больше не распространяются.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('keygen')
    p.add_argument('nick')
    p.add_argument('--target', required=True)
    p.set_defaults(f=cmd_keygen)
    p = sub.add_parser('fork')
    p.add_argument('rubric')
    p.add_argument('--from', dest='from', required=True, help='инстанс-источник реплики')
    p.add_argument('--by', required=True, help='локальный хранитель рубрики (подпись)')
    p.add_argument('--target', required=True)
    p.add_argument('--reason', required=True)
    p.set_defaults(f=cmd_fork)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
