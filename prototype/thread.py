#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thread.py — потоковый слой Живой Библиотеки (документ 15 §15.3–15.4).

Механика границы:
  * поток append-only и лёгкий: реплика = строка «ник: текст»
    (формат СОВМЕСТИМ с distill.py — это контракт, не случайность);
  * поток не хранит знания: бессмертие реплики — только через карточку;
  * «📌 в канон» = номинация, а не публикация: pin -> черновик -> ревью;
  * «полезно» — сигнал, не вердикт: нет отрицательных реакций,
    нет счётчика на реплике, агрегат виден только в дайджесте недели.

Использование:
  python3 thread.py say formy/agregatory --nick anna_p "текст реплики"
  python3 thread.py useful formy/agregatory "фрагмент реплики" --nick pavel_d
  python3 thread.py pin formy/agregatory --keeper marina_k --title "..."
  python3 thread.py show formy/agregatory
"""
import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
THREADS = os.path.join(ROOT, 'threads')
LEDGER = os.path.join(ROOT, '_ledger.log')

sys.path.insert(0, ROOT)
import distill as D  # noqa: E402


def thread_path(rubric):
    return os.path.join(THREADS, rubric.replace('/', '_') + '.md')


def next_ledger_id():
    best = 0
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding='utf-8'):
            m = re.search(r'ldg-(\d+)', line)
            if m:
                best = max(best, int(m.group(1)))
    return 'ldg-%04d' % (best + 1)


def ledger(event, fields, comment):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    line = '%s | %s | %s | %s | comment="%s"\n' % (ts, next_ledger_id(), event, fields, comment)
    open(LEDGER, 'a', encoding='utf-8').write(line)
    return line.split(' | ')[1]


def cmd_say(a):
    os.makedirs(THREADS, exist_ok=True)
    path = thread_path(a.rubric)
    new = not os.path.exists(path)
    with open(path, 'a', encoding='utf-8') as f:
        if new:
            f.write('# Поток рубрики %s\n# Поток не хранит знания: бессмертие — только через карточку (док. 15)\n\n'
                    % a.rubric)
        f.write('%s: %s\n' % (a.nick, a.text))
    print('Реплика добавлена в поток %s.' % a.rubric)
    print('Помните: поток — не источник. Если это знание — 📌 в канон: thread.py pin')
    return 0


def cmd_useful(a):
    path = thread_path(a.rubric)
    if not os.path.exists(path):
        print('Потока %s пока нет.' % a.rubric)
        return 1
    text = open(path, encoding='utf-8').read()
    if a.fragment not in text:
        print('Реплика с таким фрагментом не найдена в потоке.')
        return 1
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    log = os.path.join(THREADS, '_useful.log')
    with open(log, 'a', encoding='utf-8') as f:
        f.write('%s | %s | %s | %s\n' % (ts, a.nick, a.rubric, a.fragment[:80]))
    print('Сигнал «полезно» записан (без счётчика на реплике — вердикт выносит ревью, не толпа).')
    print('Агрегат недели увидит хранитель в дайджесте: digest.py')
    return 0


def cmd_pin(a):
    path = thread_path(a.rubric)
    if not os.path.exists(path):
        print('Потока %s пока нет — нечего номинировать.' % a.rubric)
        return 1
    print('📌 Номинация треда в канон (не публикация!):')
    rc = D.distill(path, a.rubric, a.keeper, a.title)
    if rc == 0:
        lid = ledger('author:%s | thread.pinned' % a.nick,
                     'thread=%s | keeper=%s' % (os.path.basename(path), a.keeper),
                     'тред номинирован в канон; решение — за хранителем')
        print('Журнал: %s (thread.pinned)' % lid)
    return rc


def cmd_show(a):
    path = thread_path(a.rubric)
    if not os.path.exists(path):
        print('Потока %s пока нет.' % a.rubric)
        return 1
    print(open(path, encoding='utf-8').read())
    log = os.path.join(THREADS, '_useful.log')
    if os.path.exists(log):
        marks = [l for l in open(log, encoding='utf-8') if ('| %s |' % a.rubric) in l]
        print('— сигналов «полезно» за всё время: %d (агрегат — в дайджесте недели)' % len(marks))
    return 0


def main():
    p = argparse.ArgumentParser(description='Потоковый слой (документ 15)')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('say', help='реплика в поток')
    s.add_argument('rubric')
    s.add_argument('--nick', required=True)
    s.add_argument('text')
    s.set_defaults(fn=cmd_say)
    u = sub.add_parser('useful', help='сигнал «полезно» (не вердикт)')
    u.add_argument('rubric')
    u.add_argument('fragment')
    u.add_argument('--nick', required=True)
    u.set_defaults(fn=cmd_useful)
    pn = sub.add_parser('pin', help='📌 номинировать тред в канон (черновик хранителю)')
    pn.add_argument('rubric')
    pn.add_argument('--keeper', required=True)
    pn.add_argument('--nick', default='anon')
    pn.add_argument('--title')
    pn.set_defaults(fn=cmd_pin)
    sh = sub.add_parser('show', help='показать поток')
    sh.add_argument('rubric')
    sh.set_defaults(fn=cmd_show)
    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == '__main__':
    main()
