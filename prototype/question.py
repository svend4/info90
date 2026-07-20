#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
question.py — вопросы как первоклассный объект (документ 15 §15.2).

Закрытый вопрос — это ссылка на карточку, а не текст. Словесный ответ
вопрос технически не закрывает: answer требует --card kn-....
Открытые вопросы рубрики — её публичный backlog (метрика спроса).

Использование:
  python3 question.py open "Почему каталоги проиграли поиску?" --rubric formy/katalogi --author anna_p
  python3 question.py answer q-0001 --card kn-2026-0007 --keeper igor_s
  python3 question.py list [--status open]
"""
import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = os.path.join(ROOT, 'questions')
CANON = os.path.join(ROOT, 'canon')
LEDGER = os.path.join(ROOT, '_ledger.log')


def next_id(prefix, pattern, source):
    best = 0
    if os.path.isdir(source):
        for f in os.listdir(source):
            m = re.match(pattern, f)
            if m:
                best = max(best, int(m.group(1)))
    elif os.path.exists(source):
        for line in open(source, encoding='utf-8'):
            m = re.search(pattern, line)
            if m:
                best = max(best, int(m.group(1)))
    return '%s-%04d' % (prefix, best + 1)


def ledger(event, fields, comment):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    lid = next_id('ldg', r'ldg-(\d+)', LEDGER)
    line = '%s | %s | %s | %s | comment="%s"\n' % (ts, lid, event, fields, comment)
    open(LEDGER, 'a', encoding='utf-8').write(line)
    return lid


def card_exists(card_id):
    for dirpath, _, files in os.walk(CANON):
        for f in files:
            if f.startswith(card_id + '-'):
                return True
    return False


def cmd_open(a):
    os.makedirs(QUESTIONS, exist_ok=True)
    qid = next_id('q', r'q-(\d+)\.md$', QUESTIONS)
    today = datetime.date.today().isoformat()
    title = a.text.strip().rstrip('?')[:80]
    text = """---
id: {qid}
title: "{title}"
status: open
asked_by: {author}
created_at: {today}
rubric: {rubric}
answered_by_card: ""
---

{text}
""".format(qid=qid, title=title, author=a.author, today=today,
           rubric=a.rubric, text=a.text)
    open(os.path.join(QUESTIONS, qid + '.md'), 'w', encoding='utf-8').write(text)
    lid = ledger('author:%s | question.opened' % a.author,
                 'question=%s | rubric=%s' % (qid, a.rubric),
                 'вопрос открыт, ушёл хранителям рубрики')
    print('Вопрос %s открыт (рубрика %s, журнал %s).' % (qid, a.rubric, lid))
    print('Хранители увидят его в backlog рубрики; закрывается только карточкой.')
    return 0


def cmd_answer(a):
    path = os.path.join(QUESTIONS, a.qid + '.md')
    if not os.path.exists(path):
        print('Вопрос %s не найден.' % a.qid)
        return 1
    if not card_exists(a.card):
        print('Карточка %s не найдена в каноне — ответ словами вопрос не закрывает (§15.2).' % a.card)
        return 1
    src = open(path, encoding='utf-8').read()
    src = src.replace('status: open', 'status: answered')
    src = src.replace('answered_by_card: ""', 'answered_by_card: %s' % a.card)
    open(path, 'w', encoding='utf-8').write(src)
    lid = ledger('keeper:%s | question.answered' % a.keeper,
                 'question=%s | card=%s' % (a.qid, a.card),
                 'вопрос закрыт ссылкой на карточку')
    print('Вопрос %s закрыт карточкой %s (журнал %s).' % (a.qid, a.card, lid))
    return 0


def cmd_list(a):
    if not os.path.isdir(QUESTIONS):
        print('Вопросов пока нет.')
        return 0
    n = 0
    for f in sorted(os.listdir(QUESTIONS)):
        if not f.endswith('.md'):
            continue
        src = open(os.path.join(QUESTIONS, f), encoding='utf-8').read()
        status = re.search(r'status: (\S+)', src).group(1)
        if a.status and status != a.status:
            continue
        title = re.search(r'title: "(.*)"', src).group(1)
        rubric = re.search(r'rubric: (\S+)', src).group(1)
        card = re.search(r'answered_by_card: "?(\S*?)"?\n', src).group(1)
        mark = {'open': '❓', 'answered': '✅', 'merged': '🔀'}.get(status, '?')
        print('%s %s [%s] %s — %s%s' % (mark, f[:-3], rubric, title, status,
                                        ' → ' + card if card else ''))
        n += 1
    if not n:
        print('Нет вопросов со статусом %s.' % (a.status or 'любым'))
    return 0


def main():
    p = argparse.ArgumentParser(description='Вопросы Живой Библиотеки (документ 15)')
    sub = p.add_subparsers(dest='cmd', required=True)
    o = sub.add_parser('open', help='открыть вопрос')
    o.add_argument('text')
    o.add_argument('--rubric', required=True)
    o.add_argument('--author', required=True)
    o.set_defaults(fn=cmd_open)
    an = sub.add_parser('answer', help='закрыть вопрос карточкой (не словами!)')
    an.add_argument('qid')
    an.add_argument('--card', required=True)
    an.add_argument('--keeper', required=True)
    an.set_defaults(fn=cmd_answer)
    li = sub.add_parser('list', help='список вопросов (backlog рубрик)')
    li.add_argument('--status')
    li.set_defaults(fn=cmd_list)
    args = p.parse_args()
    sys.exit(args.fn(args))


if __name__ == '__main__':
    main()
