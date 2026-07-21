#!/usr/bin/env python3
"""
Живая Библиотека — веб-обёртка поверх CLI (прототип, фаза 4).

Назначение: те же действия, что делают ask.py / question.py / propose_change.py /
review_change.py / check_freshness.py, но через браузер. Обёртка НИЧЕГО не
реализует сама: каждая кнопка вызывает соответствующий CLI-скрипт через
subprocess и показывает его вывод. Поэтому журнал власти, заявки и канон
остаются консистентными независимо от того, откуда пришло действие.

Аутентификации нет (прототип): имя автора/хранителя вводится в форму и
записывается в журнал. Доверие строится не на пароле, а на публичности журнала
(документы 04 и 18). В боевой версии сюда встаёт подпись ключом роль@инстанс
(документ 17).

Запуск:  python3 webapp.py [--port 8000]
Зависимостей нет — только стандартная библиотека Python 3.8+.
"""
import argparse, html, os, re, subprocess, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

CSS = """
:root{--bg:#faf7f2;--card:#fff;--ink:#2b2a28;--muted:#7a756d;--accent:#b3541e;--line:#e6e0d6;}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Georgia,serif;background:var(--bg);color:var(--ink);line-height:1.65}
.wrap{max-width:900px;margin:0 auto;padding:0 24px}
header{padding:28px 0 16px;border-bottom:3px double var(--line)}
h1{font-size:28px}.kick{font-family:Arial;font-size:12px;letter-spacing:3px;text-transform:uppercase;color:var(--accent)}
nav{font-family:Arial;font-size:14px;padding:12px 0;border-bottom:1px solid var(--line)}
nav a{color:var(--ink);margin-right:16px;text-decoration:none}nav a:hover{color:var(--accent)}
main{padding:24px 0 40px}
.card{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:18px;margin:12px 0}
.meta{font-family:Arial;font-size:13px;color:var(--muted)}
pre{background:#f5f1ea;border:1px solid var(--line);border-radius:6px;padding:14px;overflow:auto;font-size:13px;white-space:pre-wrap}
label{display:block;font-family:Arial;font-size:13px;color:var(--muted);margin:12px 0 4px}
input[type=text],select,textarea{width:100%;padding:8px;border:1px solid var(--line);border-radius:4px;font-size:14px;font-family:inherit;background:#fff}
textarea{font-family:monospace;font-size:13px}
button{margin-top:14px;padding:9px 20px;border:0;border-radius:4px;background:var(--accent);color:#fff;font-size:14px;cursor:pointer}
button.ret{background:#a1662f}
.out{margin-top:18px}
h2{border-bottom:1px solid var(--line);padding-bottom:6px;margin:22px 0 12px;font-size:21px}
a{color:var(--accent)}
"""

def run(cmd):
    """Вызов CLI-скрипта прототипа. Возвращает (ok, вывод)."""
    p = subprocess.run([PY] + cmd, cwd=ROOT, capture_output=True, text=True, timeout=60)
    out = (p.stdout + p.stderr).strip()
    return p.returncode == 0, out

def canon_cards():
    cards = []
    for dirpath, _, files in os.walk(os.path.join(ROOT, 'canon')):
        for f in sorted(files):
            if f.endswith('.md'):
                cards.append((f.split('-')[0] + '-' + f.split('-')[1] + '-' + f.split('-')[2]
                              if f.startswith('kn-') else f[:-3],
                              os.path.join(dirpath, f)))
    # надёжнее: id из имени kn-YYYY-NNNN-*
    out = []
    for cid, path in cards:
        m = re.match(r'(kn-\d{4}-\d{4})', os.path.basename(path))
        if m:
            out.append((m.group(1), path))
    return out

def read_card(path):
    return open(path, encoding='utf-8').read()

def list_changes():
    ch = []
    d = os.path.join(ROOT, 'changes')
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith('.md'):
                text = open(os.path.join(d, f), encoding='utf-8').read()
                state = re.search(r'^state:\s*(\w+)', text, re.M)
                card = re.search(r'^card:\s*(\S+)', text, re.M)
                ch.append((f[:-3], state.group(1) if state else '?',
                           card.group(1) if card else '?'))
    return ch

def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)} — Живая Библиотека</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><div class="kick">Живая Библиотека · веб-обёртка прототипа</div>
<h1>{html.escape(title)}</h1></header>
<nav><a href="/">Панель</a><a href="/ask">Навигатор</a><a href="/questions">Вопросы</a><a href="/changes">Заявки</a><a href="/propose">Предложить правку</a><a href="/ledger">Журнал</a></nav>
<main>{body}</main>
</div></body></html>"""

def esc_pre(out):
    return f'<pre>{html.escape(out)}</pre>'

# ---------- страницы ----------

def pg_panel():
    ok, health = run(['check_freshness.py'])
    _, qs = run(['question.py', 'list'])
    changes = list_changes()
    open_ch = [c for c in changes if c[1] == 'open']
    body = f"""
<p>Это тот же прототип, что и в CLI: каждая кнопка здесь вызывает соответствующий
скрипт (<code>ask.py</code>, <code>question.py</code>, <code>propose_change.py</code>…),
а тот пишет в журнал власти. Источник истины — файлы, не сервер.</p>
<h2>Здоровье канона</h2>{esc_pre(health)}
<h2>Открытые заявки ({len(open_ch)})</h2>
{''.join(f'<div class="card"><a href="/change?id={c[0]}">{c[0]}</a> → карточка {c[2]} <span class="meta">({c[1]})</span></div>' for c in open_ch) or '<p class="meta">Открытых заявок нет.</p>'}
<h2>Вопросы</h2>{esc_pre(qs)}
<p class="meta">Аутентификации нет: имя в форме = подпись в журнале. Доверие — публичностью, не паролем (документы 04, 18).</p>"""
    return page('Панель', body)

def pg_ask(q='', include_stale=False):
    res = ''
    if q:
        cmd = ['ask.py', q]
        if include_stale:
            cmd.append('--include-stale')
        ok, out = run(cmd)
        res = f'<h2>Ответ навигатора</h2>{esc_pre(out)}'
    body = f"""
<p>RAG-навигатор отвечает <b>только цитатами канона</b> с привязкой к карточке и разделу.
Чего нет в каноне — того нет в ответе.</p>
<form method="get" action="/ask">
<label>Вопрос</label><input type="text" name="q" value="{html.escape(q)}" required>
<label><input type="checkbox" name="stale" value="1" style="width:auto" {'checked' if include_stale else ''}> включить устаревающие карточки (с янтарной пометкой)</label>
<button>Спросить</button></form>
<div class="out">{res}</div>"""
    return page('Навигатор', body)

def pg_questions(msg=''):
    _, out = run(['question.py', 'list'])
    body = f"""
<p>Вопрос — первоклассный объект. Закрывается <b>только ссылкой на карточку</b>
(документ 15): словесный ответ вопрос не закрывает.</p>
{msg}
<h2>Открыть вопрос</h2>
<form method="post" action="/questions/open">
<label>Текст вопроса</label><input type="text" name="text" required>
<label>Рубрика (например, formy/katalogi)</label><input type="text" name="rubric" required>
<label>Ваш ник</label><input type="text" name="author" required>
<button>Открыть вопрос</button></form>
<h2>Закрыть вопрос карточкой</h2>
<form method="post" action="/questions/answer">
<label>ID вопроса (q-NNNN)</label><input type="text" name="qid" required>
<label>ID карточки (kn-YYYY-NNNN)</label><input type="text" name="card" required>
<label>Хранитель</label><input type="text" name="keeper" required>
<button>Закрыть карточкой</button></form>
<h2>Список вопросов</h2>{esc_pre(out)}"""
    return page('Вопросы', body)

def pg_changes():
    rows = ''.join(
        f'<div class="card"><a href="/change?id={cid}">{cid}</a> → {card} '
        f'<span class="meta">состояние: <b>{state}</b></span></div>'
        for cid, state, card in list_changes())
    return page('Заявки', f'<p>PR-модель: предложение → ревью хранителя → журнал.</p>{rows or "<p class=meta>Заявок нет.</p>"}')

def pg_change(ch_id, msg=''):
    path = os.path.join(ROOT, 'changes', ch_id + '.md')
    if not (re.match(r'^(ch|rq)-\d{4}$', ch_id) and os.path.exists(path)):
        return page('Заявка не найдена', '<p>Нет такой заявки.</p>')
    text = open(path, encoding='utf-8').read()
    state = re.search(r'^state:\s*(\w+)', text, re.M)
    forms = ''
    if state and state.group(1) == 'open':
        forms = f"""
<h2>Ревью (комментарий обязателен — правило 11.4)</h2>
<form method="post" action="/review">
<input type="hidden" name="ch" value="{html.escape(ch_id)}">
<label>Хранитель</label><input type="text" name="keeper" required>
<label>Комментарий</label><input type="text" name="comment" required>
<button name="action" value="accept">Принять</button>
<button name="action" value="return" class="ret">Вернуть автору</button></form>"""
    body = f'{msg}<h2>{html.escape(ch_id)}</h2>{esc_pre(text)}{forms}'
    return page('Заявка ' + ch_id, body)

def pg_propose(msg=''):
    cards = canon_cards()
    opts = ''.join(f'<option value="{cid}">{cid}</option>' for cid, _ in cards)
    body = f"""
{msg}
<p>Автор предлагает правку — хранитель ревьюит. Причина обязательна, попадёт в журнал.</p>
<form method="post" action="/propose">
<label>Карточка</label><select name="card_id">{opts}</select>
<label>Полный текст карточки с вашей правкой (текущий текст подставлен)</label>
<textarea name="text" rows="22" id="cardtext"></textarea>
<label>Причина правки</label><input type="text" name="reason" required>
<label>Ваш ник</label><input type="text" name="author" required>
<button>Создать заявку</button></form>
<script>
const texts = {{{', '.join('%r: %r' % (cid, read_card(p)) for cid, p in cards)}}};
const sel = document.querySelector('select[name=card_id]');
const ta = document.getElementById('cardtext');
const fill = () => ta.value = texts[sel.value] || '';
sel.onchange = fill; fill();
</script>"""
    return page('Предложить правку', body)

def pg_ledger():
    path = os.path.join(ROOT, '_ledger.log')
    lines = open(path, encoding='utf-8').read().strip().split('\n')
    rows = ''.join(
        '<tr>' + ''.join(f'<td>{html.escape(p.strip())}</td>' for p in l.split(' | ')) + '</tr>'
        for l in reversed(lines) if l.strip())
    body = f"""
<p>Append-only журнал власти: каждое действие ролей — кто, что, когда, почему (документ 04).</p>
<table style="width:100%;border-collapse:collapse;font-family:Arial;font-size:13px">
<tr style="text-align:left;border-bottom:2px solid var(--line)">
<th>Время</th><th>ID</th><th>Актор</th><th>Событие</th><th>Детали</th></tr>
{rows}</table>
<style>td,th{{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}}</style>"""
    return page('Журнал власти', body)

# ---------- сервер ----------

class Handler(BaseHTTPRequestHandler):
    def _send(self, text, code=200):
        data = text.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _form(self):
        n = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(n).decode('utf-8')
        from urllib.parse import unquote_plus
        out = {}
        for pair in raw.split('&'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                out[unquote_plus(k)] = unquote_plus(v)
        return out

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == '/':
            self._send(pg_panel())
        elif u.path == '/ask':
            self._send(pg_ask(q.get('q', [''])[0], 'stale' in q))
        elif u.path == '/questions':
            self._send(pg_questions())
        elif u.path == '/changes':
            self._send(pg_changes())
        elif u.path == '/change':
            self._send(pg_change(q.get('id', [''])[0]))
        elif u.path == '/propose':
            self._send(pg_propose())
        elif u.path == '/ledger':
            self._send(pg_ledger())
        else:
            self._send(page('404', '<p>Нет такой страницы.</p>'), 404)

    def do_POST(self):
        u = urlparse(self.path)
        f = self._form()
        if u.path == '/questions/open':
            ok, out = run(['question.py', 'open', f.get('text', ''),
                           '--rubric', f.get('rubric', ''), '--author', f.get('author', '')])
            msg = f'<div class="card">{esc_pre(out)}</div>'
            self._send(pg_questions(msg))
        elif u.path == '/questions/answer':
            ok, out = run(['question.py', 'answer', f.get('qid', ''),
                           '--card', f.get('card', ''), '--keeper', f.get('keeper', '')])
            msg = f'<div class="card">{esc_pre(out)}</div>'
            self._send(pg_questions(msg))
        elif u.path == '/propose':
            tmp = os.path.join(ROOT, 'inbox', '_webapp-edit.md')
            open(tmp, 'w', encoding='utf-8').write(f.get('text', ''))
            ok, out = run(['propose_change.py', f.get('card_id', ''), tmp,
                           f.get('reason', ''), '--author', f.get('author', '')])
            try:
                os.remove(tmp)
            except OSError:
                pass
            self._send(pg_propose(f'<div class="card">{esc_pre(out)}</div>'))
        elif u.path == '/review':
            ok, out = run(['review_change.py', f.get('action', ''), f.get('ch', ''),
                           '--keeper', f.get('keeper', ''), '--comment', f.get('comment', '')])
            self._send(pg_change(f.get('ch', ''), f'<div class="card">{esc_pre(out)}</div>'))
        else:
            self._send(page('404', '<p>Нет такого действия.</p>'), 404)

    def log_message(self, *a):
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8000)
    a = ap.parse_args()
    print(f'Веб-обёртка Живой Библиотеки: http://localhost:{a.port}/  (Ctrl+C — стоп)')
    HTTPServer(('127.0.0.1', a.port), Handler).serve_forever()

if __name__ == '__main__':
    main()
