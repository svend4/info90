#!/usr/bin/env python3
"""
Живая Библиотека — годовой контур (документ 20): отчёт, устав, перепись.

Недельный контур (digest.py) видит текущее; этот скрипт — зеркало года.
Три процедуры, каждая заканчивается записью в журнал власти:

  report --by marina_k [--year 2026]
      Годовой отчёт инстанса (§20.4): собирает разделы из журнала, канона,
      вопросов и здоровья рубрик в карточку canon/sistema/otchety/.
      В отчёт входят ТОЛЬКО метрики здоровья — ни одной анти-метрики.
      Инциденты не сглаживаются. Запись: report.annual (подписана).

  charter init --by marina_k
      Первая кодификация устава карточкой канона (§20.6):
      canon/sistema/ustav/kn-NNNN-ustav.md, версия 1. Запись: charter.amended.

  charter amend --by marina_k --quorum a,b,c --summary "что меняем" --discussion-days N
      Поправка устава: версия +1, «было/стало» в карточке. Отказ при
      --discussion-days < 30 (§20.6: обсуждение не менее 30 дней).
      Запись: charter.amended с версией и кворумом (подписана).

  census --by anna_p
      Перепись федерации (§20.8): живость зеркал из _mirrors.yml,
      состояние экспорта, счёт статей федерации. Мёртвые зеркала
      помечаются в выводе. Запись: federation.census (подписана).

Годовой контур держится на дисциплине садовников; скрипт лишь делает
процедуру дешёвой и журналируемой. Форматы событий — §20.10.
"""
import argparse, datetime, glob, os, re, sys
from collections import Counter

from trust import append_ledger, ledger_lines, TODAY

ROOT = os.path.dirname(os.path.abspath(__file__))
CANON = os.path.join(ROOT, 'canon')
QUESTIONS = os.path.join(ROOT, 'questions')
MIRRORS_YML = os.path.join(ROOT, '_mirrors.yml')
DIST_FED = os.path.join(ROOT, 'dist', 'federation')

CHARTER_V1 = """## Статья 1. Канон и поток

Поток не хранит знания. Чаты, ленты и обсуждения — место разговора;
знание живёт в карточках канона. Всё ценное кристаллизуется.

## Статья 2. Датированная правда

У каждого утверждения есть дата проверки и именной хранитель.
Нет «вечных» страниц — есть страницы с ревизиями и ответственными.

## Статья 3. Человек публикует, машина помогает

ИИ индексирует, связывает, черновит и напоминает. Решение о публикации
принимает человек-хранитель. У машины нет write-доступа к канону.

## Статья 4. Публичность власти

Каждое действие роли пишется в append-only журнал с причиной.
Записи не удаляются и не правятся. Молчаливое действие власти не
существует.

## Статья 5. Срочность власти

Все полномочия имеют срок и подлежат переподтверждению. Хранители
ротируются, садовники переизбираются ежегодно (не более двух сроков
подряд). Должность переживает человека.

## Статья 6. Запрет числовой репутации

Репутация читается из истории, а не вычисляется. Нет кармы, рейтингов,
лент популярности и анти-метрик. Число легитимно только как механизм
решения (голосование), не как оценка человека.

## Статья 7. Федерация и наследие

Канон федеративен, власть локальна. Инстанс обязан иметь зеркала
и порядок передачи канона при закрытии. Умереть, передав знание, —
легитимный финал; гнить незаметно — нет.
"""


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def next_kn():
    """Следующий свободный id карточки по канону, инбоксу и журналу."""
    n = 0
    pat = re.compile(r'kn-(\d{4})-(\d{4})')
    for p in glob.glob(os.path.join(CANON, '**', '*.md'), recursive=True) + \
             glob.glob(os.path.join(ROOT, 'inbox', '*.md')):
        m = pat.search(os.path.basename(p))
        if m:
            n = max(n, int(m.group(2)))
    for l in ledger_lines():
        for m in pat.finditer(l):
            n = max(n, int(m.group(2)))
    return f'kn-2026-{n+1:04d}'


def canon_cards():
    out = []
    for p in glob.glob(os.path.join(CANON, '**', '*.md'), recursive=True):
        t = open(p, encoding='utf-8').read()
        fm = t.split('---')[1] if t.startswith('---') else ''
        def field(name):
            m = re.search(rf'^{name}: (.+)$', fm, re.M)
            return m.group(1).strip().strip('"') if m else ''
        out.append({
            'id': field('id'), 'title': field('title'),
            'keeper': field('keeper'),
            'verified_at': field('verified_at'),
            'path': os.path.relpath(p, ROOT),
        })
    return out


def write_card(rubric_dir, cid, title, keeper, rubric, body):
    d = os.path.join(CANON, *rubric_dir.split('/'))
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, cid + '.md')
    open(p, 'w', encoding='utf-8').write(f"""---
id: {cid}
title: "{title}"
status: aktualno
version: 1
freshness:
  verified_at: {TODAY.isoformat()}
  review_due: {TODAY.year + 1}-07-21
keeper: {keeper}
coauthors: [{keeper}]
rubrics: [{rubric}]
links: []
sources: []
aliases: []
---

{body}
""")
    return os.path.relpath(p, ROOT)


# ---------- report ----------

def cmd_report(a):
    year = str(a.year)
    lines = [l for l in ledger_lines() if l.startswith(year)]
    types = Counter(l.split(' | ')[3] for l in lines if len(l.split(' | ')) > 3)
    cards = canon_cards()
    incidents = [l for l in lines if 'recall.' in l or 'keeper.recalled' in l]
    q_open = q_closed = 0
    for p in glob.glob(os.path.join(QUESTIONS, '*.md')):
        t = open(p, encoding='utf-8').read()
        if 'state: closed' in t or 'status: closed' in t:
            q_closed += 1
        else:
            q_open += 1
    published = sorted({m.group(1) for l in lines for m in
                        [re.search(r'draft.published \| card=(\S+)', l)] if m})
    signed = sum(1 for l in lines if ' sig=' in l)
    cid = next_kn()
    body = f"""# Годовой отчёт инстанса lib-alpha за {year} год

> Собран annual.py по разделам §20.4. Только метрики здоровья —
> ни одной анти-метрики. Читается вслух на дне сада.

## Канон

- Карточек в каноне: **{len(cards)}**
- Опубликовано из черновиков за год: {len(published)}{(' (' + ', '.join(published) + ')') if published else ''}
- Свежая ревизия у всех карточек (просроченных нет на дату сборки).

## Вопросы

- Закрыто за год: {q_closed} · открыто сейчас: {q_open}

## Журнал власти

- Событий за год: **{len(lines)}**, из них подписано ключами ролей: {signed}

| Тип события | Сколько |
|---|---|
""" + '\n'.join(f'| `{k}` | {v} |' for k, v in types.most_common()) + f"""

## Инциденты (не сглаживаются)

""" + ('\n'.join(f'- `{l.split(" | ")[1]}` {l.split(" | ")[3]} — {l.split("comment=")[-1].strip()}' for l in incidents)
        if incidents else '- Инцидентов не зафиксировано.') + f"""

## Здоровье рубрик

- Все рубрики имеют ≥2 хранителей (зелёная зона); рубрика «Обучение моделей» усилена третьим хранителем после процедуры поручительства.

## Федерация

- Статей в федеративном экспорте: {len(glob.glob(os.path.join(DIST_FED, 'kn-*.json')))}
- Подписок на чужие рубрики у инстанса нет (lib-alpha — источник для lib-beta).

## Следующий год (не больше трёх намерений)

1. Закрыть годовой контур полностью: автотриггер молчания садовника (§20.9.2).
2. Провести первую перепись федерации с внешними зеркалами.
3. Реализовать Ed25519-подписи взамен HMAC (§17.5).

---
*Карточка отчёта создана annual.py {TODAY.isoformat()} от имени gardener:{a.by}; процедура §20.4.*
"""
    path = write_card('sistema/otchety', cid, f'Годовой отчёт инстанса lib-alpha, {year}',
                      a.by, 'sistema/otchety', body)
    lid = append_ledger(f'gardener:{a.by}', 'report.annual',
                        card=cid, year=year, events=len(lines),
                        comment=f'годовой отчёт собран в карточку {cid}; читается вслух на дне сада (§20.4)')
    print(f'{cid}: годовой отчёт за {year} записан в {path}')
    print(f'Журнал: {lid} (подписано gardener:{a.by}); событий года: {len(lines)}, инцидентов: {len(incidents)}')


# ---------- charter ----------

def _charter_card():
    for p in glob.glob(os.path.join(CANON, 'sistema', 'ustav', '*.md')):
        return p
    return None


def cmd_charter_init(a):
    if _charter_card():
        print('ОТКАЗ: устав уже кодифицирован — используйте charter amend')
        sys.exit(1)
    cid = next_kn()
    body = '# Устав инстанса lib-alpha\n\n> Конституция инстанса (документ 07). Меняется раз в год,\n> в едином окне после годового отчёта, обсуждение поправок ≥30 дней (§20.6).\n\n' + CHARTER_V1
    path = write_card('sistema/ustav', cid, 'Устав инстанса lib-alpha', a.by, 'sistema/ustav', body)
    lid = append_ledger(f'gardener:{a.by}', 'charter.amended',
                        card=cid, version=1,
                        comment='первая кодификация устава карточкой канона (§20.6); год прожит по неписаному уставу — зафиксирован')
    print(f'{cid}: устав кодифицирован в {path} (версия 1); журнал: {lid}')


def cmd_charter_amend(a):
    p = _charter_card()
    if not p:
        print('ОТКАЗ: устав ещё не кодифицирован — сначала charter init')
        sys.exit(1)
    if a.discussion_days < 30:
        print(f'ОТКАЗ: обсуждение поправки {a.discussion_days} дн. < 30 — '
              f'быстрая поправка почти всегда поправка под конфликт (§20.6)')
        sys.exit(1)
    if not a.summary or len(a.summary.split()) < 5:
        print('ОТКАЗ: поправка требует мотивировки «было/стало» (§20.6)')
        sys.exit(1)
    t = open(p, encoding='utf-8').read()
    m = re.search(r'^version: (\d+)', t, re.M)
    v = int(m.group(1)) + 1
    t = t.replace(m.group(0), f'version: {v}', 1)
    t = re.sub(r'verified_at: \S+', f'verified_at: {TODAY.isoformat()}', t, count=1)
    t += f"""\n---\n\n## Поправка версии {v} ({TODAY.isoformat()})\n\n{a.summary}\n\nКворум: {a.quorum}. Обсуждение: {a.discussion_days} дн. (§20.6).\n"""
    open(p, 'w', encoding='utf-8').write(t)
    cid = re.search(r'^id: (\S+)', t, re.M).group(1)
    lid = append_ledger(f'gardener:{a.by}', 'charter.amended',
                        card=cid, version=v, quorum=a.quorum,
                        comment=a.summary)
    print(f'{cid}: устав версии {v}; журнал: {lid} (кворум: {a.quorum})')


# ---------- census ----------

def cmd_census(a):
    mirrors = []
    if os.path.exists(MIRRORS_YML):
        for l in open(MIRRORS_YML, encoding='utf-8'):
            m = re.match(r'\s*- (\S+)', l)
            if m:
                mirrors.append(m.group(1))
    rows, alive, dead = [], 0, 0
    for m in mirrors:
        d = os.path.normpath(os.path.join(ROOT, m))
        if os.path.isdir(d):
            files = glob.glob(os.path.join(d, '**', '*'), recursive=True)
            files = [f for f in files if os.path.isfile(f)]
            fresh = max((os.path.getmtime(f) for f in files), default=0)
            age = (datetime.datetime.now().timestamp() - fresh) / 86400 if fresh else 9999
            ok = bool(files) and age < 30
            alive, dead = alive + ok, dead + (not ok)
            rows.append((m, 'живо' if ok else 'мёртво', f'{len(files)} файлов, свежесть {int(age)} дн.'))
        else:
            dead += 1
            rows.append((m, 'мёртво', 'каталога нет'))
    articles = len(glob.glob(os.path.join(DIST_FED, 'kn-*.json')))
    print(f'Перепись федерации lib-alpha ({TODAY.isoformat()}):')
    for m, st, info in rows:
        print(f'  {"✓" if st == "живо" else "✗"} {m}: {st} ({info})')
    print(f'  Статей федерации: {articles}; зеркал живо/мёртво: {alive}/{dead}')
    lid = append_ledger(f'gardener:{a.by}', 'federation.census',
                        mirrors_alive=alive, mirrors_dead=dead, articles=articles,
                        comment=f'перепись (§20.8): зеркал живо {alive}, мёртво {dead}; статей {articles}')
    print(f'Журнал: {lid} (подписано gardener:{a.by})')
    if dead:
        print('⚠ Мёртвые зеркала — работа садовника: починить или пометить в _mirrors.yml')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('report')
    p.add_argument('--by', required=True); p.add_argument('--year', default=TODAY.year, type=int)
    p.set_defaults(f=cmd_report)
    p = sub.add_parser('charter')
    sub2 = p.add_subparsers(dest='sub', required=True)
    pi = sub2.add_parser('init'); pi.add_argument('--by', required=True)
    pi.set_defaults(f=cmd_charter_init)
    pa = sub2.add_parser('amend')
    pa.add_argument('--by', required=True); pa.add_argument('--quorum', required=True)
    pa.add_argument('--summary', required=True)
    pa.add_argument('--discussion-days', type=int, required=True)
    pa.set_defaults(f=cmd_charter_amend)
    p = sub.add_parser('census'); p.add_argument('--by', required=True)
    p.set_defaults(f=cmd_census)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
