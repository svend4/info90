#!/usr/bin/env python3
"""
Живая Библиотека — подписка на чужую рубрику (документ 17, протокол федерации).

Читает outbox другого инстанса (OrderedCollection с Announce-элементами,
как делает federate.py) и складывает карточки-реплики в
    <target>/replicas/<instance>/kn-....md

Железные правила протокола (документ 17):
1. Реплика НИКОГДА не попадает в локальный canon/ — она read-only.
2. Статус не наследуется: у реплики нет нашего статуса, есть origin_* поля.
3. Если локальный канон уже содержит карточку с таким id — локальная побеждает,
   реплика не создаётся (конфликт пишется в _sync.log).
4. Обновление — только если origin_version выше уже сохранённой.
5. Удаление НЕ распространяется: исчезнувшая из outbox карточка не удаляется,
   а помечается origin_missing_at — чужая цензура не стирает нашу копию.

Запуск:
  python3 subscribe.py --outbox <outbox.json> --articles-dir <dir> \
      --instance lib-alpha --target /path/to/our-instance

Аутентичность в прототипе не проверяется (нет подписей); в боевой версии
Article подписан ключом хранителя роль@инстанс (документ 17 §5).
"""
import argparse, datetime, json, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def article_path(articles_dir, announce):
    ref = announce.get('object', '')
    cid = ref.rstrip('/').split('/')[-1]
    p = os.path.join(articles_dir, cid + '.json')
    return cid, p if os.path.exists(p) else None


def parse_replica_head(path):
    """origin_version из существующей реплики (для сравнения версий)."""
    if not os.path.exists(path):
        return None
    text = open(path, encoding='utf-8').read()
    m = re.search(r'^origin_version:\s*(\d+)', text, re.M)
    return int(m.group(1)) if m else 0


def local_canon_ids(target):
    ids = set()
    canon = os.path.join(target, 'canon')
    for dirpath, _, files in os.walk(canon):
        for f in files:
            m = re.match(r'(kn-\d{4}-\d{4})', f)
            if m:
                ids.add(m.group(1))
    return ids


def keeper_from_actor(url):
    return url.rstrip('/').split('/')[-1] if url else '—'


def sync_log(rep_dir, event, detail):
    ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(os.path.join(rep_dir, '_sync.log'), 'a', encoding='utf-8') as f:
        f.write(f'{ts} | {event} | {detail}\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--outbox', required=True, help='путь к outbox-<rubric>.json чужого инстанса')
    ap.add_argument('--articles-dir', required=True, help='каталог с Article-документами (kn-*.json)')
    ap.add_argument('--instance', required=True, help='имя инстанса-источника (метка реплик)')
    ap.add_argument('--target', default=ROOT, help='корень НАШЕГО инстанса (по умолчанию — этот)')
    a = ap.parse_args()

    today = datetime.date.today().isoformat()
    outbox = load_json(a.outbox)
    items = outbox.get('orderedItems', outbox.get('items', []))
    rep_dir = os.path.join(a.target, 'replicas', a.instance)
    os.makedirs(rep_dir, exist_ok=True)
    canon_ids = local_canon_ids(a.target)

    stats = {'new': 0, 'updated': 0, 'skipped_conflict': 0, 'skipped_fresh': 0, 'missing': 0}
    seen = set()

    for it in items:
        if it.get('type') != 'Announce':
            continue
        cid, apath = article_path(a.articles_dir, it)
        seen.add(cid)
        if apath is None:
            print(f'  !! {cid}: Article-документ не найден, пропуск')
            continue
        art = load_json(apath)

        if cid in canon_ids:
            stats['skipped_conflict'] += 1
            sync_log(rep_dir, 'replica.conflict', f'{cid} | локальный канон содержит этот id — реплика отклонена')
            print(f'  ⊗ {cid}: конфликт id с локальным каноном — локальная версия побеждает')
            continue

        dest = os.path.join(rep_dir, cid + '.md')
        src = art.get('source', {})
        body = src.get('content', '') if isinstance(src, dict) else str(src)
        o_ver = art.get('zh:version', 1)
        try:
            o_ver = int(o_ver)
        except (TypeError, ValueError):
            o_ver = 1

        old_ver = parse_replica_head(dest)
        if old_ver is not None and old_ver >= o_ver:
            # карточка снова в outbox — снять пометку исчезновения, если была
            if os.path.exists(dest):
                cur = open(dest, encoding='utf-8').read()
                if 'origin_missing_at' in cur:
                    cur = re.sub(r'^origin_missing_at:.*\n', '', cur, flags=re.M)
                    open(dest, 'w', encoding='utf-8').write(cur)
                    sync_log(rep_dir, 'replica.origin_back', f'{cid} | оригинал снова в outbox, пометка снята')
                    print(f'  ↩ {cid}: оригинал вернулся в outbox — пометка исчезновения снята')
            stats['skipped_fresh'] += 1
            continue

        text = f"""---
id: {cid}
title: "{art.get('name', cid)}"
replica: true
readonly: true
origin: {art.get('id', '').split('/federation/')[0]}
origin_instance: {a.instance}
origin_keeper: {keeper_from_actor(art.get('attributedTo', ''))}
origin_status: {art.get('zh:status', '?')}
origin_version: {o_ver}
origin_review_due: {art.get('zh:reviewDue', '?')}
fetched_at: {today}
rubrics: [{', '.join(t.get('name', '') for t in art.get('tag', []) if isinstance(t, dict))}]
---

> **Реплика read-only** инстанса `{a.instance}` (документ 17).
> Статус `{art.get('zh:status', '?')}` — статус ОРИГИНАЛА, не наш; доверие не наследуется.
> Правки сюда не вносятся: предложение изменения уходит хранителю оригинала
> (@{keeper_from_actor(art.get('attributedTo', ''))}@{a.instance}).

{body}
"""
        open(dest, 'w', encoding='utf-8').write(text)
        if old_ver is None:
            stats['new'] += 1
            sync_log(rep_dir, 'replica.added', f'{cid} | origin_version={o_ver}')
            print(f'  + {cid}: реплика создана (оригинал v{o_ver})')
        else:
            stats['updated'] += 1
            sync_log(rep_dir, 'replica.updated', f'{cid} | v{old_ver} -> v{o_ver}')
            print(f'  ↑ {cid}: реплика обновлена v{old_ver} → v{o_ver}')

    # правило 5: исчезновение из outbox — не удаление, а пометка.
    # Проверяются только реплики ЭТОЙ рубрики (outbox — порубричный):
    # карточка соседней рубрики в этом outbox не обязана быть.
    rubric = os.path.basename(a.outbox)[len('outbox-'):-len('.json')].replace('_', '/')
    for f in os.listdir(rep_dir):
        m = re.match(r'(kn-\d{4}-\d{4})\.md$', f)
        if not m or m.group(1) in seen:
            continue
        p = os.path.join(rep_dir, f)
        text = open(p, encoding='utf-8').read()
        if rubric not in (re.search(r'^rubrics:\s*\[(.*)\]', text, re.M).group(1)
                          if re.search(r'^rubrics:\s*\[(.*)\]', text, re.M) else ''):
            continue
        if 'origin_missing_at' in text:
            continue
        text = re.sub(r'^(fetched_at:.*)$', r'\1\norigin_missing_at: ' + today, text, count=1, flags=re.M)
        open(p, 'w', encoding='utf-8').write(text)
        stats['missing'] += 1
        sync_log(rep_dir, 'replica.origin_missing',
                 f'{m.group(1)} | исчезла из outbox оригинала; копия сохранена (удаление не распространяется)')
        print(f'  ⚠ {m.group(1)}: оригинал исчез из outbox — реплика сохранена и помечена')

    sync_log(rep_dir, 'replica.synced',
             f'outbox={os.path.basename(a.outbox)} | new={stats["new"]} upd={stats["updated"]} '
             f'conflict={stats["skipped_conflict"]} fresh={stats["skipped_fresh"]} missing={stats["missing"]}')
    print(f"Подписка {a.instance}: +{stats['new']} новых, ↑{stats['updated']} обновлено, "
          f"⊗{stats['skipped_conflict']} конфликтов, ⚠{stats['missing']} исчезнувших. "
          f"Журнал: {os.path.relpath(os.path.join(rep_dir, '_sync.log'), a.target)}")


if __name__ == '__main__':
    main()
