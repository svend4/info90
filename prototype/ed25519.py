#!/usr/bin/env python3
"""
ed25519.py — подписи Ed25519 на чистом Python (RFC 8032), без зависимостей.

Эталонная (медленная) реализация из RFC 8032, адаптированная для журнала
Живой Библиотеки: подписываются короткие строки событий, поэтому скорости
чистого Python достаточно (~0.1–0.3 с на подпись/проверку).

Честная граница (та же, что в документе 17 §5): это справочная реализация
для прототипа; боевой вариант — libsodium/OpenSSH через системные вызовы.
Ключи: 32-байтовый seed (приватный, не коммитится), 32-байтовый публичный
ключ (коммитится в _keys/registry.yml — асимметрия позволяет проверять
подписи всем, не зная секрета; с HMAC это было невозможно).
"""
import hashlib

_b = 256
_q = 2**255 - 19
_l = 2**252 + 27742317777372353535851937790883648493


def _H(m):
    return hashlib.sha512(m).digest()


def _inv(x):
    return pow(x, _q - 2, _q)


_d = (-121665 * _inv(121666)) % _q
_I = pow(2, (_q - 1) // 4, _q)


def _xrecover(y):
    xx = (y * y - 1) * _inv(_d * y * y + 1)
    x = pow(xx, (_q + 3) // 8, _q)
    if (x * x - xx) % _q != 0:
        x = (x * _I) % _q
    if x % 2 != 0:
        x = _q - x
    return x


_By = (4 * _inv(5)) % _q
_Bx = _xrecover(_By)
_B = (_Bx % _q, _By % _q)
_O = (0, 1)  # нейтральный элемент


def _edwards(P, Q):
    (x1, y1) = P
    (x2, y2) = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _d * x1 * x2 * y1 * y2)
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _d * x1 * x2 * y1 * y2)
    return (x3 % _q, y3 % _q)


def _scalarmult(P, e):
    """Итеративное double-and-add (быстрее рекурсии из RFC)."""
    R = _O
    Q = P
    while e > 0:
        if e & 1:
            R = _edwards(R, Q)
        Q = _edwards(Q, Q)
        e >>= 1
    return R


def _encodeint(y):
    return y.to_bytes(32, 'little')


def _encodepoint(P):
    (x, y) = P
    bits = bytearray(_encodeint(y))
    bits[31] |= (x & 1) << 7
    return bytes(bits)


def _bit(h, i):
    return (h[i // 8] >> (i % 8)) & 1


def publickey(seed):
    """seed: 32 байта -> публичный ключ (32 байта)."""
    h = _H(seed)
    a = 2**(_b - 2) + sum(2**i * _bit(h, i) for i in range(3, _b - 2))
    A = _scalarmult(_B, a)
    return _encodepoint(A)


def _Hint(m):
    return int.from_bytes(_H(m), 'little')


def signature(m, seed, pk):
    """m: bytes -> подпись (64 байта)."""
    h = _H(seed)
    a = 2**(_b - 2) + sum(2**i * _bit(h, i) for i in range(3, _b - 2))
    r = _Hint(h[_b // 8:_b // 4] + m)
    R = _scalarmult(_B, r)
    S = (r + _Hint(_encodepoint(R) + pk + m) * a) % _l
    return _encodepoint(R) + _encodeint(S)


def _isoncurve(P):
    (x, y) = P
    return (-x * x + y * y - 1 - _d * x * x * y * y) % _q == 0


def _decodeint(s):
    return int.from_bytes(s, 'little')


def _decodepoint(s):
    y = _decodeint(s) & (2**(_b - 1) - 1)
    x = _xrecover(y)
    if x & 1 != _bit(s, _b - 1):
        x = _q - x
    P = (x, y)
    if not _isoncurve(P):
        raise ValueError('точка не на кривой')
    return P


def checkvalid(sig, m, pk):
    """Проверка подписи; True/False (исключения = подпись невалидна)."""
    if len(sig) != 64 or len(pk) != 32:
        return False
    try:
        R = _decodepoint(sig[:32])
        A = _decodepoint(pk)
    except ValueError:
        return False
    S = _decodeint(sig[32:])
    h = _Hint(sig[:32] + pk + m)
    return _scalarmult(_B, S) == _edwards(R, _scalarmult(A, h))


# --- самотест при запуске напрямую ---
if __name__ == '__main__':
    import os, time
    seed = os.urandom(32)
    pk = publickey(seed)
    t0 = time.time()
    sig = signature('zh-lib selftest'.encode(), seed, pk)
    ok = checkvalid(sig, 'zh-lib selftest'.encode(), pk)
    bad = checkvalid(sig, 'zh-lib SELFTEST изменено'.encode(), pk)
    dt = time.time() - t0
    print(f'подпись+проверка: {"OK" if ok else "ПРОВАЛ"}; '
          f'изменённое сообщение: {"ОТКЛОНЕНО (OK)" if not bad else "ПРИНЯТО (ПРОВАЛ)"}; '
          f'{dt:.2f} с')
