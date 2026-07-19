#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ask.py — RAG-навигатор Живой Библиотеки (фаза 2, документ 10 §10.4).

Принципы:
  * отвечает ТОЛЬКО цитатами из карточек канона (экстрактивный ответ);
  * каждое утверждение привязано к card_id — пост-проверка встроена
    в саму механику: вне цитат навигатор ничего не говорит;
  * карточки со статусом ustarevaet/trebuet-revizii исключаются,
    либо включаются с янтарной пометкой (--include-stale);
  * если релевантных чанков нет — честное «в каноне этого нет»
    + совет открыть вопрос (вопрос -> карточка, документ 03).

Zero-dependency: вместо векторного индекса — BM25-подобный скоринг
по токенам (демо-замена гибридного поиска из §10.4; интерфейс ответа
и дисциплина цитирования — те же).

Использование:
  python3 ask.py "как устроена модерация в реддите"
  python3 ask.py "что такое переобучение" --include-stale --top 3
"""
import argparse
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build import load_cards  # noqa: E402

MIN_SCORE = 1.0          # ниже — считаем, что в каноне ответа нет
STALE = ('ustarevaet', 'trebuet-revizii')

STOP = set("""
и в во не что на я с он а как это то все она так его но да ты к у же вы за бы по только
ее мне было вот от меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни
быть был него до вас нибудь опять уж вам ведь там потом себя ничего ей может они тут где
есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет ж
тогда кто этот того потому этого какой совсем ним здесь этом один почти мой тем чтобы нее
сейчас были куда зачем всех никогда можно при наконец два об другой хоть после над больше
тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой
перед иногда лучше чуть том нельзя такой им более всегда конечно всю между
the a an of to in is are was were for on with as at by it this that from or and be not
""".split())


def tokenize(text):
    return [t for t in re.findall(r'[a-zа-яё0-9]+', text.lower()) if t not in STOP and len(t) > 1]


def chunk_card(card):
    """Карточка -> чанки по разделам (§-якоря), плюс вводный чанк."""
    chunks = []
    body = card['body_raw']
    parts = re.split(r'(?m)^(## .+)$', body)
    intro = parts[0].strip()
    if intro:
        chunks.append({'card': card, 'anchor': 'введение', 'text': intro})
    i = 1
    while i + 1 < len(parts):
        title = parts[i].lstrip('# ').strip()
        chunks.append({'card': card, 'anchor': title, 'text': parts[i + 1].strip()})
        i += 2
    return chunks


def build_index(cards):
    chunks = []
    for c in cards:
        chunks.extend(chunk_card(c))
    df = {}
    for ch in chunks:
        for t in set(tokenize(ch['text'] + ' ' + ch['card'].get('title', ''))):
            df[t] = df.get(t, 0) + 1
    return chunks, df


def bm25(query_tokens, chunk, df, n_chunks):
    toks = tokenize(chunk['text'] + ' ' + chunk['card'].get('title', '')
                    + ' ' + ' '.join(chunk['card'].get('aliases', [])))
    if not toks:
        return 0.0
    tf = {}
    for t in toks:
        tf[t] = tf.get(t, 0) + 1
    k1, b, avgdl = 1.5, 0.75, 220.0
    score = 0.0
    for q in query_tokens:
        if q not in tf:
            continue
        idf = math.log(1 + (n_chunks - df.get(q, 0) + 0.5) / (df.get(q, 0) + 0.5))
        score += idf * (tf[q] * (k1 + 1)) / (tf[q] + k1 * (1 - b + b * len(toks) / avgdl))
    return score


def quote(text, limit=420):
    """Чистая цитата: первые предложения чанка без markdown-разметки."""
    plain = re.sub(r'[*`#>\[\]()]', '', text)
    plain = re.sub(r'\s+', ' ', plain).strip()
    if len(plain) > limit:
        plain = plain[:limit].rsplit(' ', 1)[0] + '…'
    return plain


def answer(question, top=4, include_stale=False):
    cards = load_cards()
    chunks, df = build_index(cards)
    q_tokens = tokenize(question)
    scored = []
    for ch in chunks:
        status = ch['card'].get('status', '')
        if status in STALE and not include_stale:
            continue  # фильтр свежести (§10.4)
        s = bm25(q_tokens, ch, df, len(chunks))
        if s >= MIN_SCORE:
            scored.append((s, ch))
    scored.sort(key=lambda x: -x[0])

    if not scored:
        print(f"Вопрос: {question}\n")
        print("В каноне этого нет. Навигатор не отвечает вне карточек —")
        print("это принцип, а не сбой. Что можно сделать:")
        print("  1. Открыть вопрос (question.opened) — он попадёт хранителям рубрики;")
        print("  2. Если есть готовый материал — python3 distill.py <файл> создаст черновик.")
        return 1

    print(f"Вопрос: {question}\n")
    print("Ответ (только по карточкам канона, каждый тезис — цитата):\n")
    seen_cards = []
    for rank, (s, ch) in enumerate(scored[:top], 1):
        m = ch['card']
        amber = ' ⚠️ [статус: %s — данные могли устареть]' % m['status'] if m['status'] in STALE else ''
        print(f"{rank}. [{m['id']} §{ch['anchor']}]{amber}")
        print(f"   «{quote(ch['text'])}»\n")
        if m['id'] not in seen_cards:
            seen_cards.append(m['id'])
    print('—' * 60)
    print("Источники (проверьте даты — доверие = свежесть):")
    for cid in seen_cards:
        card = next(c for c in cards if c['id'] == cid)
        m = card
        print(f"  · {m['id']} «{m['title']}» — v{m['version']}, "
              f"проверено {m['freshness']['verified_at']}, статус: {m['status']}")
    return 0


def main():
    p = argparse.ArgumentParser(description='RAG-навигатор по канону Живой Библиотеки')
    p.add_argument('question')
    p.add_argument('--top', type=int, default=4)
    p.add_argument('--include-stale', action='store_true',
                   help='включать устаревающие карточки (с янтарной пометкой)')
    a = p.parse_args()
    sys.exit(answer(a.question, a.top, a.include_stale))


if __name__ == '__main__':
    main()
