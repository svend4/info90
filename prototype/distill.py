#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
distill.py — ИИ-дистилляция: тред (чат/форум) -> черновик карточки.

Фаза 2, документ 10 §10.4 («ДИСТИЛЛЯЦИЯ ЧАТА»):
  тред -> выделение решения/фактов -> черновик карточки
  (проблема -> причина -> решение -> источники)
  -> соавторы = участники треда -> заявка хранителю

Железное правило реализации (§10.4): у дистиллятора НЕТ write-доступа
к канону. Он пишет только в inbox/ (черновики-заявки) и журнал.
Публикацию совершает человек-хранитель через review_change.py.

Zero-dependency демо: вместо LLM — детерминированные эвристики
(детектор URL, маркеры решений, участники). Интерфейс и дисциплина
«машина черновит, человек публикует» — те же, что и у боевой версии.

Использование:
  python3 distill.py inbox/sample-thread.md --rubric formy/agregatory --keeper igor_s
"""
import argparse
import datetime
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(ROOT, 'inbox')
CANON = os.path.join(ROOT, 'canon')
LEDGER = os.path.join(ROOT, '_ledger.log')

# Маркеры для эвристик (боевой вариант заменит их LLM, контракт тот же)
PROBLEM_MARKERS = ('проблем', 'не работает', 'сломал', 'ошибка', 'баг', 'вопрос:',
                   'как сделать', 'почему', 'не могу', 'помогите')
SOLUTION_MARKERS = ('решил', 'решение', 'помогло', 'исправил', 'надо ', 'нужно ',
                    'оказалось', 'работает:', 'ответ:', 'вывод', 'итог')
CAUSE_MARKERS = ('причин', 'оказалось, что', 'дело в том', 'из-за', 'потому что',
                 'корень', 'виноват')


def next_card_id():
    year = datetime.date.today().year
    best = 0
    for base in (CANON, INBOX):
        if not os.path.isdir(base):
            continue
        for dirpath, _, files in os.walk(base):
            for f in files:
                m = re.match(r'kn-%d-(\d+)' % year, f)
                if m:
                    best = max(best, int(m.group(1)))
    return 'kn-%d-%04d' % (year, best + 1)


def next_ledger_id():
    best = 0
    if os.path.exists(LEDGER):
        for line in open(LEDGER, encoding='utf-8'):
            m = re.search(r'ldg-(\d+)', line)
            if m:
                best = max(best, int(m.group(1)))
    return 'ldg-%04d' % (best + 1)


def parse_thread(text):
    """Тред -> реплики вида 'ник: текст' (пустая строка = разделитель реплик)."""
    msgs = []
    nick, buf = None, []
    for line in text.splitlines():
        m = re.match(r'^\s*(?:\[[^\]]*\]\s*)?([A-Za-z0-9_\-]{2,32}):\s+(.*)$', line)
        if m:
            if nick is not None:
                msgs.append((nick, ' '.join(buf).strip()))
            nick, buf = m.group(1), [m.group(2)]
        elif line.strip():
            buf.append(line.strip())
        elif nick is not None:
            msgs.append((nick, ' '.join(buf).strip()))
            nick, buf = None, []
    if nick is not None:
        msgs.append((nick, ' '.join(buf).strip()))
    return msgs


def pick(msgs, markers, limit=4):
    hits = []
    for nick, text in msgs:
        low = text.lower()
        if any(k in low for k in markers):
            hits.append('**%s:** %s' % (nick, text))
        if len(hits) >= limit:
            break
    return hits


def distill(thread_path, rubric, keeper, title=None):
    text = open(thread_path, encoding='utf-8').read()
    msgs = parse_thread(text)
    if not msgs:
        print('Не удалось разобрать тред: нужны реплики вида «ник: текст».')
        return 1

    participants = sorted({n for n, _ in msgs})
    urls = sorted(set(re.findall(r'https?://[^\s)\]>"\']+', text)))
    problems = pick(msgs, PROBLEM_MARKERS)
    causes = pick(msgs, CAUSE_MARKERS)
    solutions = pick(msgs, SOLUTION_MARKERS)

    card_id = next_card_id()
    today = datetime.date.today().isoformat()
    title = title or 'Дистилляция треда: ' + os.path.basename(thread_path)
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    if not slug:  # кириллический заголовок — латинского слага нет
        slug = 'chernovik'

    def section(items, placeholder):
        return '\n'.join('- ' + i for i in items) if items else '_%s (заполняет хранитель)_' % placeholder

    draft = """---
id: {cid}
title: "{title}"
status: chernovik
version: 1
freshness:
  verified_at: {today}
  review_due: {due}
keeper: {keeper}
coauthors: [{coauthors}]
rubrics: [{rubric}]
links: []
sources:{sources}
aliases: []
---

> Черновик, дистиллированный машиной из треда «{src}» ({n} реплик, {p} участников).
> Машина только черновит — публикует человек-хранитель (правило §10.4).

## Проблема

{problems}

## Причина

{causes}

## Решение

{solutions}

## Источники

{src_list}

---
*Черновик: distill.py {today}. Требует ревизии хранителя {keeper} перед переносом в канон.*
""".format(
        cid=card_id, title=title, today=today,
        due=(datetime.date.today() + datetime.timedelta(days=90)).isoformat(),
        keeper=keeper, coauthors=', '.join(participants), rubric=rubric,
        sources=('\n' + '\n'.join('  - {url: "%s", title: "из треда", checked: %s}' % (u, today)
                                  for u in urls)) if urls else ' []',
        src=os.path.basename(thread_path), n=len(msgs), p=len(participants),
        problems=section(problems, 'Проблема не извлечена автоматически'),
        causes=section(causes, 'Причина не извлечена автоматически'),
        solutions=section(solutions, 'Решение не извлечено автоматически'),
        src_list=('\n'.join('- ' + u for u in urls)) if urls else '_В треде ссылок не найдено_',
    )

    os.makedirs(INBOX, exist_ok=True)
    out = os.path.join(INBOX, '%s-%s.md' % (card_id, slug))
    open(out, 'w', encoding='utf-8').write(draft)

    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    line = ('%s | %s | distill.py | question.distilled | card=%s | rubric=%s | '
            'source=%s | participants=%d | comment="черновик в inbox/, ждёт хранителя %s"\n'
            % (ts, next_ledger_id(), card_id, rubric,
               os.path.basename(thread_path), len(participants), keeper))
    open(LEDGER, 'a', encoding='utf-8').write(line)

    print('Черновик создан:', os.path.relpath(out, ROOT))
    print('  карточка: %s, статус chernovik, соавторы: %s' % (card_id, ', '.join(participants)))
    print('  журнал: %s (question.distilled)' % line.split(' | ')[1])
    print('Дальше — только человек: хранитель %s читает черновик и решает.' % keeper)
    return 0


def main():
    p = argparse.ArgumentParser(description='Дистилляция треда в черновик карточки (только inbox/)')
    p.add_argument('thread', help='файл с тредом (реплики вида «ник: текст»)')
    p.add_argument('--rubric', required=True, help='рубрика, например formy/agregatory')
    p.add_argument('--keeper', required=True, help='ник хранителя-получателя заявки')
    p.add_argument('--title', help='заголовок карточки')
    a = p.parse_args()
    sys.exit(distill(a.thread, a.rubric, a.keeper, a.title))


if __name__ == '__main__':
    main()
