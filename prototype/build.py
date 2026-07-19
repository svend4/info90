#!/usr/bin/env python3
"""
Живая Библиотека — прототип Фазы 0.
Статический генератор канона: Markdown-карточки + YAML-фронтматтер -> HTML.
Зависимостей нет (только стандартная библиотека Python 3.8+).

Запуск:  python3 build.py
Результат: папка dist/ — статический сайт (главная, рубрики, карточки).
"""
import os, re, html, shutil, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
CANON = os.path.join(ROOT, "canon")
DIST = os.path.join(ROOT, "dist")

# ---------- мини-парсер фронтматтера (подмножество YAML прототипа) ----------

def parse_inline(val):
    val = val.strip()
    if val.startswith('['):
        return [x.strip().strip('"').strip("'") for x in val.strip('[]').split(',') if x.strip()]
    if val.startswith('{'):
        d = {}
        for part in val.strip('{}').split(','):
            k, _, v = part.partition(':')
            d[k.strip()] = v.strip().strip('"').strip("'")
        return d
    return val.strip('"').strip("'")

def parse_frontmatter(text):
    data, lines, i = {}, text.split('\n'), 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1; continue
        m = re.match(r'^(\w[\w-]*):\s*(.*)$', line)
        if not m:
            i += 1; continue
        key, val = m.group(1), m.group(2).strip()
        if val:
            data[key] = parse_inline(val); i += 1; continue
        # вложенный блок или список
        items, nested = [], {}
        i += 1
        while i < len(lines) and (lines[i].startswith('  ') or lines[i].strip().startswith('- ')):
            l = lines[i].strip()
            if l.startswith('- '):
                items.append(parse_inline(l[2:]))
            else:
                k, _, v = l.partition(':')
                nested[k.strip()] = parse_inline(v)
            i += 1
        data[key] = items if items else nested
    return data

def split_card(text):
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.S)
    if not m:
        raise ValueError("нет фронтматтера")
    return parse_frontmatter(m.group(1)), m.group(2).strip()

# ---------- мини-конвертер Markdown -> HTML (подмножество) ----------

def md_inline(s):
    s = html.escape(s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return s

def md_to_html(md):
    out, lines, i = [], md.split('\n'), 0
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            i += 1; continue
        if l.startswith('#'):
            lvl = len(l) - len(l.lstrip('#'))
            out.append(f'<h{min(lvl,4)}>{md_inline(l[lvl:].strip())}</h{min(lvl,4)}>'); i += 1
        elif re.match(r'^\d+\.\s', l):
            items = []
            while i < len(lines) and re.match(r'^\d+\.\s', lines[i]):
                items.append(f'<li>{md_inline(re.sub(r"^\\d+\\.\\s", "", lines[i]))}</li>'); i += 1
            out.append('<ol>' + ''.join(items) + '</ol>')
        elif l.lstrip().startswith('- '):
            items = []
            while i < len(lines) and lines[i].lstrip().startswith('- '):
                items.append(f'<li>{md_inline(lines[i].lstrip()[2:])}</li>'); i += 1
            out.append('<ul>' + ''.join(items) + '</ul>')
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not lines[i].startswith('#') \
                  and not lines[i].lstrip().startswith('- ') and not re.match(r'^\d+\.\s', lines[i]):
                para.append(lines[i].strip()); i += 1
            out.append(f'<p>{md_inline(" ".join(para))}</p>')
    return '\n'.join(out)

# ---------- загрузка карточек и рубрик ----------

def load_cards():
    cards = []
    for dirpath, _, files in os.walk(CANON):
        for f in sorted(files):
            if not f.endswith('.md'):
                continue
            text = open(os.path.join(dirpath, f), encoding='utf-8').read()
            meta, body = split_card(text)
            meta['slug'] = meta['id']
            meta['body_html'] = md_to_html(body)
            meta['file'] = f
            cards.append(meta)
    return cards

def load_rubrics():
    text = open(os.path.join(ROOT, '_rubrics.yml'), encoding='utf-8').read()
    rubrics, stack = [], []
    for line in text.split('\n'):
        if not line.strip() or line.strip().startswith('#') or line.strip() == 'rubrics:':
            continue
        indent = len(line) - len(line.lstrip())
        k, _, v = line.strip().partition(':')
        k, v = k.strip(), v.strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        ctx = stack[-1][1] if stack else None
        if k == '- id':
            r = {'id': v, 'title': '', 'keeper': '', 'parent': ctx}
            rubrics.append(r)
            if ctx is not None:
                ctx.setdefault('children', []).append(r)
            stack.append((indent, r))
        elif stack and k in ('title', 'keeper'):
            stack[-1][1][k] = v
    return rubrics

# ---------- шаблоны ----------

STATUS = {
    'aktualno': ('✅ Актуально', '#2e7d4f'),
    'ustarevaet': ('⚠️ Устаревает', '#b3541e'),
    'trebuet-revizii': ('🔍 Требует ревизии', '#a1662f'),
    'chernovik': ('✏️ Черновик', '#7a756d'),
}

CSS = """
:root{--bg:#faf7f2;--card:#fff;--ink:#2b2a28;--muted:#7a756d;--accent:#b3541e;--line:#e6e0d6;}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Georgia,serif;background:var(--bg);color:var(--ink);line-height:1.65}
.wrap{max-width:900px;margin:0 auto;padding:0 24px}
header{padding:36px 0 20px;border-bottom:3px double var(--line)}
h1{font-size:34px}.kick{font-family:Arial;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--accent)}
nav{font-family:Arial;font-size:14px;padding:12px 0;border-bottom:1px solid var(--line)}
nav a{color:var(--ink);margin-right:18px;text-decoration:none}nav a:hover{color:var(--accent)}
main{padding:28px 0 40px}
.banner{font-family:Arial;font-size:13px;padding:8px 14px;border-radius:4px;margin:18px 0;display:inline-block;color:#fff}
.meta{font-family:Arial;font-size:13px;color:var(--muted);margin:6px 0 20px}
.meta b{color:var(--ink)}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:20px;margin:14px 0}
.card h3{font-size:18px;margin-bottom:6px}
.card a{color:var(--accent);text-decoration:none}
.card .st{font-family:Arial;font-size:11px;padding:2px 8px;border-radius:3px;color:#fff}
h2{border-bottom:1px solid var(--line);padding-bottom:8px;margin:26px 0 14px;font-size:24px}
article h2{border:none;margin:20px 0 8px;padding:0;font-size:21px}
article h3{font-size:17px;margin:16px 0 6px}
article p{margin:10px 0}article ul,article ol{margin:10px 0 10px 24px}
article li{margin:4px 0}
.links li, .src li{font-size:14px}
footer{border-top:1px solid var(--line);margin-top:40px;padding:20px 0 34px;font-family:Arial;font-size:13px;color:var(--muted)}
code{background:#f0ebe2;padding:1px 5px;border-radius:3px;font-size:14px}
a{color:var(--accent)}
"""

def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — Живая Библиотека (прототип)</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><div class="kick">Живая Библиотека · Прототип фазы 0</div>
<h1>{html.escape(title)}</h1></header>
<nav><a href="index.html">Главная</a><a href="index.html#rubrics">Рубрики</a><a href="index.html#cards">Карточки</a></nav>
<main>{body}</main>
<footer>Сгенерировано build.py · Канон = Markdown + Git · Каждое утверждение имеет дату и хранителя</footer>
</div></body></html>"""

def card_page(c):
    st, color = STATUS.get(c.get('status', 'chernovik'), STATUS['chernovik'])
    fr = c.get('freshness', {})
    links = ''.join(
        f'<li>{l.get("type","связь")} → <a href="{l.get("to")}.html">{l.get("to")}</a></li>'
        for l in c.get('links', []) if isinstance(l, dict))
    srcs = ''.join(
        f'<li><a href="{s.get("url","#")}">{s.get("title","источник")}</a> (проверен {s.get("checked","—")})</li>'
        for s in c.get('sources', []) if isinstance(s, dict))
    coa = ', '.join('@' + x for x in c.get('coauthors', []))
    body = f"""
<span class="banner" style="background:{color}">{st}</span>
<div class="meta">Проверено: <b>{fr.get('verified_at','—')}</b> · Ревизия до: <b>{fr.get('review_due','—')}</b> ·
Хранитель: <b>@{c.get('keeper','—')}</b> · Версия {c.get('version','1')} · Рубрика: {', '.join(c.get('rubrics',[]))}</div>
<article>{c['body_html']}</article>
{f'<h2>Связи</h2><ul class="links">{links}</ul>' if links else ''}
{f'<h2>Источники</h2><ul class="src">{srcs}</ul>' if srcs else ''}
<div class="meta" style="margin-top:24px">Соавторы: {coa or '—'} · ID: {c['id']}</div>"""
    return page(c['title'], body)

def index_page(cards, rubrics):
    def rubric_html(r, depth=0):
        count = sum(1 for c in cards if r['id'] in c.get('rubrics', []))
        kids = ''.join(rubric_html(k, depth+1) for k in r.get('children', []))
        pad = ' style="margin-left:%dpx"' % (depth*20) if depth else ''
        return f'<div class="card"{pad}><b>{r["title"]}</b> <span class="meta">({count} 📄 · хранитель @{r["keeper"] or "—"})</span>{kids}</div>'
    top = [r for r in rubrics if r['parent'] is None]
    rub = ''.join(rubric_html(r) for r in top)
    fresh = sorted(cards, key=lambda c: c.get('freshness', {}).get('verified_at', ''), reverse=True)
    cl = ''.join(
        f'<div class="card"><h3><a href="{c["slug"]}.html">{c["title"]}</a></h3>'
        f'<span class="st" style="background:{STATUS.get(c.get("status","chernovik"),STATUS["chernovik"])[1]}">'
        f'{STATUS.get(c.get("status","chernovik"),STATUS["chernovik"])[0]}</span> '
        f'<span class="meta">проверено {c.get("freshness",{}).get("verified_at","—")} · @{c.get("keeper","—")}</span></div>'
        for c in fresh)
    body = f"""
<p>Это работающий прототип Живой Библиотеки: карточки знаний хранятся как Markdown-файлы
с метаданными в Git-репозитории, а этот сайт собирается из них одним скриптом
(<code>python3 build.py</code>). Документы проекта — в папке
<a href="../zhivaya-biblioteka/README.md">zhivaya-biblioteka/</a>.</p>
<h2 id="rubrics">Рубрики</h2>{rub}
<h2 id="cards">Карточки канона (по свежести проверки)</h2>{cl}"""
    return page('Канон', body)

# ---------- сборка ----------

def main():
    cards, rubrics = load_cards(), load_rubrics()
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    open(os.path.join(DIST, 'index.html'), 'w', encoding='utf-8').write(index_page(cards, rubrics))
    for c in cards:
        open(os.path.join(DIST, c['slug'] + '.html'), 'w', encoding='utf-8').write(card_page(c))
    print(f"OK: {len(cards)} карточек, {len(rubrics)} рубрик -> dist/ "
          f"({datetime.date.today().isoformat()})")

if __name__ == '__main__':
    main()
