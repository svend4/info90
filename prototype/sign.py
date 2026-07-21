#!/usr/bin/env python3
"""
Живая Библиотека — ключи и подписи действий власти (документы 17 §5, 18).

Веб-обёртка и CLI принимают имя как подпись. Этот модуль превращает имя
в проверяемую подпись: у актора есть ключ `_keys/<nick>.key`, каждая новая
запись журнала от его имени получает поле `sig=` — HMAC-SHA256 от содержимого
записи. Любая задним числом изменённая строка перестаёт сходиться — журнал
становится tamper-evident, не переставая быть append-only.

Честная граница прототипа: HMAC симметричен — проверить подпись может тот,
у кого есть ключ (сам инстанс). В боевой версии (документ 17 §5) вместо
HMAC — Ed25519: приватный ключ у роли, публичный — в actors.json федерации,
проверка не требует секрета. Формат поля sig= и процедуры от этого не меняются.

Команды:
  keygen <nick> [--instance NAME]   # создать ключ + запись в реестре + событие в журнале
  fingerprint <nick>                # отпечаток ключа (первые 16 hex sha256)
  verify-ledger [--file PATH]       # проверить все sig= в журнале; exit 1 при подделке
"""
import argparse, datetime, hashlib, hmac, os, re, secrets, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(ROOT, '_keys')
REGISTRY = os.path.join(KEYS, 'registry.yml')
LEDGER = os.path.join(ROOT, '_ledger.log')


def key_path(nick):
    return os.path.join(KEYS, nick + '.key')


def load_key(nick):
    p = key_path(nick)
    if not os.path.exists(p):
        return None
    return open(p, encoding='utf-8').read().strip()


def fingerprint(key):
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]


def sign(key, payload):
    return hmac.new(key.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:32]


def sign_line(nick, line):
    """Добавить sig= к строке журнала, если у ника есть ключ. Иначе — как есть."""
    key = load_key(nick)
    if not key or ' | sig=' in line:
        return line
    return line + ' | sig=' + sign(key, line)


def actor_nick(actor):
    """keeper:marina_k -> marina_k; distill.py -> None (у машины нет ключа)."""
    m = re.match(r'^(author|keeper|gardener):(\S+)$', actor)
    return m.group(2) if m else None


def cmd_keygen(a):
    os.makedirs(KEYS, exist_ok=True)
    if os.path.exists(key_path(a.nick)):
        print(f'ОТКАЗ: ключ {a.nick} уже существует (смена ключа — отдельная процедура, §17.5)')
        sys.exit(1)
    key = secrets.token_hex(32)
    p = key_path(a.nick)
    open(p, 'w', encoding='utf-8').write(key + '\n')
    os.chmod(p, 0o600)
    fp = fingerprint(key)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(REGISTRY, 'a', encoding='utf-8') as f:
        f.write(f'- nick: {a.nick}\n  instance: {a.instance}\n  fingerprint: {fp}\n  created_at: {ts}\n')
    # событие в журнал — первым же ключом подписано быть не может, это регистрация
    with open(LEDGER, 'a', encoding='utf-8') as f:
        n = 1
        for l in open(LEDGER, encoding='utf-8'):
            m = re.search(r'ldg-(\d+)', l)
            if m:
                n = max(n, int(m.group(1)) + 1)
        f.write(f'{ts} | ldg-{n:04d} | system | key.registered | nick={a.nick} | '
                f'instance={a.instance} | fingerprint={fp} | '
                f'comment="ключ роли зарегистрирован; действия теперь подписываются (§17.5)"\n')
    print(f'Ключ создан: {os.path.relpath(p, ROOT)} (права 600, не коммитить!)')
    print(f'Отпечаток: {fp} — в _keys/registry.yml и журнале (ldg-{n:04d})')


def cmd_fingerprint(a):
    key = load_key(a.nick)
    if not key:
        print(f'Нет ключа для {a.nick}')
        sys.exit(1)
    print(f'{a.nick}: {fingerprint(key)}')


def cmd_verify_ledger(a):
    path = a.file or LEDGER
    signed = unsigned = bad = 0
    bad_lines = []
    for i, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line.strip():
            continue
        if ' | sig=' not in line:
            unsigned += 1
            continue
        body, sig = line.rsplit(' | sig=', 1)
        parts = [p.strip() for p in body.split(' | ')]
        nick = actor_nick(parts[2]) if len(parts) >= 3 else None
        key = load_key(nick) if nick else None
        if not key or not hmac.compare_digest(sign(key, body), sig.strip()):
            bad += 1
            bad_lines.append(i)
        else:
            signed += 1
    print(f'Проверено {path}:')
    print(f'  подписанных верных: {signed}')
    print(f'  без подписи (старые/машинные): {unsigned}')
    print(f'  ПОДДЕЛЬНЫХ: {bad}' + (f' — строки {bad_lines}' if bad else ''))
    if bad:
        print('ЖУРНАЛ СКОМПРОМЕТИРОВАН: записи изменены задним числом или ключи не те.')
        sys.exit(1)
    print('Целостность подписанных записей подтверждена.')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('keygen')
    p.add_argument('nick'); p.add_argument('--instance', default='lib-alpha')
    p.set_defaults(f=cmd_keygen)
    p = sub.add_parser('fingerprint')
    p.add_argument('nick')
    p.set_defaults(f=cmd_fingerprint)
    p = sub.add_parser('verify-ledger')
    p.add_argument('--file', default=None)
    p.set_defaults(f=cmd_verify_ledger)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
