#!/usr/bin/env python3
"""
Живая Библиотека — ключи и подписи действий власти (документы 17 §5, 18).

Версия 2 — Ed25519 (асимметричные подписи, RFC 8032, чистый Python в
ed25519.py). У роли есть приватный seed `_keys/<nick>.ed25519` (не
коммитится), публичный ключ — в `_keys/registry.yml` (коммитится:
проверка подписи больше не требует секрета — с симметричным HMAC это
было невозможно, в этом и был смысл апгрейда §17.5).

Форматы подписи в журнале:
  * ` | edsig=<128 hex>` — Ed25519, проверяется публичным ключом из реестра;
  * ` | sig=<32 hex>`   — legacy HMAC-SHA256 (записи до апгрейда), проверяется
                          локальным ключом `_keys/<nick>.key`.
Журнал append-only: старые HMAC-записи НЕ переподписываются — они остаются
историей со своей честной границей; новые действия ролей подписываются Ed25519.

Честная граница прототипа: ed25519.py — справочная (медленная) реализация
RFC 8032 без зависимостей; боевой вариант — libsodium/OpenSSH (§17.5).
Процедуры и формат журнала от замены библиотеки не меняются.

Команды:
  keygen <nick> [--instance NAME]    # legacy HMAC-ключ (для совместимости)
  keygen-ed25519 <nick> [--instance] # Ed25519: seed + публичный ключ в реестр + key.upgraded
  fingerprint <nick>                 # отпечатки ключей ника
  verify-ledger [--file PATH]        # проверить edsig= и sig= в журнале; exit 1 при подделке
"""
import argparse, datetime, hashlib, hmac, os, re, secrets, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYS = os.path.join(ROOT, '_keys')
REGISTRY = os.path.join(KEYS, 'registry.yml')
LEDGER = os.path.join(ROOT, '_ledger.log')


# ---------- legacy HMAC ----------

def key_path(nick):
    return os.path.join(KEYS, nick + '.key')


def load_key(nick):
    p = key_path(nick)
    if not os.path.exists(p):
        return None
    return open(p, encoding='utf-8').read().strip()


def fingerprint(key):
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]


def sign_hmac(key, payload):
    return hmac.new(key.encode('utf-8'), payload.encode('utf-8'), hashlib.sha256).hexdigest()[:32]


# ---------- Ed25519 ----------

def ed_key_path(nick):
    return os.path.join(KEYS, nick + '.ed25519')


def load_ed_seed(nick):
    p = ed_key_path(nick)
    if not os.path.exists(p):
        return None
    return bytes.fromhex(open(p, encoding='utf-8').read().strip())


def ed_public_from_registry(nick):
    """Публичный ключ ника из реестра (последний, если было обновление)."""
    if not os.path.exists(REGISTRY):
        return None
    pub = None
    cur = None
    for line in open(REGISTRY, encoding='utf-8'):
        m = re.match(r'^- nick: (\S+)', line)
        if m:
            cur = m.group(1)
        m = re.match(r'^\s+ed25519: ([0-9a-f]{64})', line)
        if m and cur == nick:
            pub = m.group(1)
    return bytes.fromhex(pub) if pub else None


def sign_ed(seed, payload):
    import ed25519
    pk = ed25519.publickey(seed)
    return ed25519.signature(payload.encode('utf-8'), seed, pk).hex()


# ---------- общее ----------

def sign_line(nick, line):
    """Подписать строку журнала: Ed25519, если есть новый ключ; иначе legacy HMAC."""
    if ' | sig=' in line or ' | edsig=' in line:
        return line
    seed = load_ed_seed(nick)
    if seed:
        return line + ' | edsig=' + sign_ed(seed, line)
    key = load_key(nick)
    if key:
        return line + ' | sig=' + sign_hmac(key, line)
    return line


def actor_nick(actor):
    """keeper:marina_k -> marina_k; distill.py -> None (у машины нет ключа)."""
    m = re.match(r'^(author|keeper|gardener):(\S+)$', actor)
    return m.group(2) if m else None


def _next_ledger_id():
    n = 1
    for l in open(LEDGER, encoding='utf-8'):
        m = re.search(r'ldg-(\d+)', l)
        if m:
            n = max(n, int(m.group(1)) + 1)
    return n


# ---------- команды ----------

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
    with open(LEDGER, 'a', encoding='utf-8') as f:
        n = _next_ledger_id()
        f.write(f'{ts} | ldg-{n:04d} | system | key.registered | nick={a.nick} | '
                f'instance={a.instance} | fingerprint={fp} | '
                f'comment="ключ роли зарегистрирован; действия теперь подписываются (§17.5)"\n')
    print(f'Ключ создан: {os.path.relpath(p, ROOT)} (права 600, не коммитить!)')
    print(f'Отпечаток: {fp} — в _keys/registry.yml и журнале (ldg-{n:04d})')


def cmd_keygen_ed25519(a):
    import ed25519
    os.makedirs(KEYS, exist_ok=True)
    if os.path.exists(ed_key_path(a.nick)):
        print(f'ОТКАЗ: Ed25519-ключ {a.nick} уже существует (ротация — отдельная процедура, §17.5)')
        sys.exit(1)
    seed = secrets.token_bytes(32)
    pk = ed25519.publickey(seed)
    p = ed_key_path(a.nick)
    open(p, 'w', encoding='utf-8').write(seed.hex() + '\n')
    os.chmod(p, 0o600)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(REGISTRY, 'a', encoding='utf-8') as f:
        f.write(f'- nick: {a.nick}\n  instance: {a.instance}\n  ed25519: {pk.hex()}\n  created_at: {ts}\n')
    # key.upgraded подписано НОВЫМ ключом — самоподпись доказывает владение приватным
    n = _next_ledger_id()
    line = (f'{ts} | ldg-{n:04d} | keeper:{a.nick} | key.upgraded | nick={a.nick} | '
            f'ed25519={pk.hex()[:16]}… | comment="апгрейд HMAC→Ed25519 (§17.5): публичный ключ в реестре, '
            f'проверка подписи не требует секрета; старые sig= остаются валидными"')
    line = line + ' | edsig=' + sign_ed(seed, line)
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(f'Ed25519-ключ создан: {os.path.relpath(p, ROOT)} (права 600, не коммитить!)')
    print(f'Публичный ключ: {pk.hex()}')
    print(f'— в _keys/registry.yml (можно коммитить) и журнале (ldg-{n:04d}, самоподпись)')


def cmd_fingerprint(a):
    found = False
    key = load_key(a.nick)
    if key:
        print(f'{a.nick}: HMAC legacy, отпечаток {fingerprint(key)}')
        found = True
    pub = ed_public_from_registry(a.nick)
    if pub:
        print(f'{a.nick}: Ed25519, публичный ключ {pub.hex()}')
        found = True
    if not found:
        print(f'Нет ключей для {a.nick}')
        sys.exit(1)


def cmd_verify_ledger(a):
    import ed25519
    path = a.file or LEDGER
    ed_ok = hmac_ok = unsigned = bad = 0
    bad_lines = []
    for i, line in enumerate(open(path, encoding='utf-8'), 1):
        line = line.rstrip('\n')
        if not line.strip():
            continue
        if ' | edsig=' in line:
            body, sig = line.rsplit(' | edsig=', 1)
            parts = [p.strip() for p in body.split(' | ')]
            nick = actor_nick(parts[2]) if len(parts) >= 3 else None
            pub = ed_public_from_registry(nick) if nick else None
            try:
                ok = bool(pub) and ed25519.checkvalid(bytes.fromhex(sig.strip()),
                                                      body.encode('utf-8'), pub)
            except Exception:
                ok = False
            if ok:
                ed_ok += 1
            else:
                bad += 1
                bad_lines.append(i)
        elif ' | sig=' in line:
            body, sig = line.rsplit(' | sig=', 1)
            parts = [p.strip() for p in body.split(' | ')]
            nick = actor_nick(parts[2]) if len(parts) >= 3 else None
            key = load_key(nick) if nick else None
            if not key or not hmac.compare_digest(sign_hmac(key, body), sig.strip()):
                bad += 1
                bad_lines.append(i)
            else:
                hmac_ok += 1
        else:
            unsigned += 1
    print(f'Проверено {path}:')
    print(f'  Ed25519 верных: {ed_ok}')
    print(f'  legacy HMAC верных: {hmac_ok}')
    print(f'  без подписи (старые/машинные): {unsigned}')
    print(f'  ПОДДЕЛЬНЫХ: {bad}' + (f' — строки {bad_lines}' if bad else ''))
    if bad:
        print('ЖУРНАЛ СКОМПРОМЕТИРОВАН: записи изменены задним числом или ключи не те.')
        sys.exit(1)
    print('Целостность подписанных записей подтверждена (публичная проверка — без секретов).')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('keygen')
    p.add_argument('nick'); p.add_argument('--instance', default='lib-alpha')
    p.set_defaults(f=cmd_keygen)
    p = sub.add_parser('keygen-ed25519')
    p.add_argument('nick'); p.add_argument('--instance', default='lib-alpha')
    p.set_defaults(f=cmd_keygen_ed25519)
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
