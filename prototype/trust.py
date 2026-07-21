#!/usr/bin/env python3
"""
Живая Библиотека — процедуры доверия (документ 18).

Репутация не вычисляется — она читается. Этот скрипт не считает баллы:
он проводит ПРОЦЕДУРЫ и оставляет в журнале записи с именами, датами
и причинами. Форматы событий — из §18.10, обратно совместимы с _ledger.log.

Команды:
  vouch <кандидат> --rubric R --voucher V --text "рекомендация"
      Поручительство (§18.4): только действующий хранитель, лимит 2/год.
  appoint <кандидат> --rubric R --gardener G
      Назначение хранителем: нужны ДВА разных поручителя (§18.4).
  recall open <хранитель> --rubric R --by X --reason "..." --evidence ldg-NNNN[,ldg-NNNN]
      Открытие recall (§18.5): без ссылок на журнал — отказ; квота 1/квартал;
      инициатор с двумя dismissed подряд за год — заблокирован.
  recall close rc-NNNN --decision recalled|dismissed --by G --quorum a,b,c --reason "мотивировка"
      Закрытие recall с полной мотивировкой (§18.5).
  rotation-check [--days 90]
      Кто из хранителей молчит в журнале дольше N дней (§18.3, ротация).
  rotation-apply [--days 90]
      Тихий выход спящих хранителей: keeper.rotated reason=inactivity,
      без позора; рубрику ниже 2 хранителей не опускаем без --force.
  thanks <кому> --by X --text "за что конкретно"
      Благодарность-запись (§20.7): не бейдж и не число, а строка журнала
      thanks.recorded с именем и причиной; читается в следе человека.

Записи процедур — файлы trust/v-NNNN.md и trust/rc-NNNN.md;
факты власти — только в _ledger.log.
"""
import argparse, datetime, os, re, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, '_ledger.log')
RUBRICS = os.path.join(ROOT, '_rubrics.yml')
TRUST = os.path.join(ROOT, 'trust')

TODAY = datetime.date.today()


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def ledger_lines():
    if not os.path.exists(LEDGER):
        return []
    return [l.rstrip('\n') for l in open(LEDGER, encoding='utf-8') if l.strip()]


def append_ledger(actor, event, **kv):
    n = 0
    for l in ledger_lines():
        m = re.search(r'ldg-(\d+)', l)
        if m:
            n = max(n, int(m.group(1)))
    parts = [now(), f'ldg-{n+1:04d}', actor, event]
    for k, v in kv.items():
        v = str(v)
        parts.append(f'{k}="{v}"' if ' ' in v else f'{k}={v}')
    line = ' | '.join(parts)
    try:
        import sign as _sign
        nick = _sign.actor_nick(actor)
        if nick:
            line = _sign.sign_line(nick, line)
    except ImportError:
        pass
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    return f'ldg-{n+1:04d}'


def rubrics_text():
    return open(RUBRICS, encoding='utf-8').read()


def keepers_of(rubric, text=None):
    """Список хранителей рубрики из _rubrics.yml."""
    text = text if text is not None else rubrics_text()
    m = re.search(r'- id: ' + re.escape(rubric) + r'\n(?:.*\n)*?\s*keepers: \[(.*?)\]', text)
    return [x.strip() for x in m.group(1).split(',') if x.strip()] if m else None


def all_keepers(text=None):
    text = text if text is not None else rubrics_text()
    ks = set()
    for m in re.finditer(r'keepers: \[(.*?)\]', text):
        ks.update(x.strip() for x in m.group(1).split(',') if x.strip())
    return ks


def set_keepers(rubric, new_list):
    """Переписать строку keepers рубрики в _rubrics.yml."""
    text = rubrics_text()
    pat = re.compile(r'(- id: ' + re.escape(rubric) + r'\n(?:.*\n)*?\s*keepers: )\[(.*?)\]')
    new_text, n = pat.subn(lambda m: m.group(1) + '[' + ', '.join(new_list) + ']', text, count=1)
    if n != 1:
        print(f'ОШИБКА: рубрика {rubric} не найдена в _rubrics.yml')
        sys.exit(1)
    open(RUBRICS, 'w', encoding='utf-8').write(new_text)


def next_id(prefix, kind):
    os.makedirs(TRUST, exist_ok=True)
    n = 0
    for f in os.listdir(TRUST):
        m = re.match(prefix + r'-(\d{4})\.md', f)
        if m:
            n = max(n, int(m.group(1)))
    return f'{prefix}-{n+1:04d}'


def active_vouches(candidate, rubric):
    """Поручительства за кандидата в рубрику: [(voucher, id)], списываются назначением."""
    if not os.path.isdir(TRUST):
        return []
    out = []
    for f in sorted(os.listdir(TRUST)):
        if not f.startswith('v-'):
            continue
        t = open(os.path.join(TRUST, f), encoding='utf-8').read()
        st = re.search(r'^state: (\w+)', t, re.M)
        cand = re.search(r'^candidate: (\S+)', t, re.M)
        rub = re.search(r'^rubric: (\S+)', t, re.M)
        vou = re.search(r'^voucher: (\S+)', t, re.M)
        if st and st.group(1) == 'active' and cand and cand.group(1) == candidate \
           and rub and rub.group(1) == rubric and vou:
            out.append((vou.group(1), f[:-3]))
    return out


def year_events(event, **match):
    """События журнала за текущий календарный год, отфильтрованные по key=val."""
    year = str(TODAY.year)
    for l in ledger_lines():
        if not l.startswith(year):
            continue
        parts = [p.strip() for p in l.split(' | ')]
        if len(parts) < 4 or parts[3] != event:
            continue
        if all(f'{k}={v}' in l or f'{k}="{v}"' in l for k, v in match.items()):
            yield l


def actor_history(nick):
    """Даты всех действий с участием ника (actor или ключ keeper=/by=/voucher=)."""
    days = []
    for l in ledger_lines():
        if re.search(r'(author|keeper|gardener):' + re.escape(nick) + r'\b', l) \
           or re.search(r'(keeper|voucher|by)=' + re.escape(nick) + r'\b', l):
            try:
                days.append(datetime.date.fromisoformat(l[:10]))
            except ValueError:
                pass
    return days


# ---------- команды ----------

def cmd_vouch(a):
    if a.voucher not in all_keepers():
        print(f'ОТКАЗ: {a.voucher} не действующий хранитель — поручаться не может (§18.4)')
        sys.exit(1)
    if keepers_of(a.rubric) is None:
        print(f'ОТКАЗ: рубрики {a.rubric} нет в _rubrics.yml')
        sys.exit(1)
    if a.candidate in (keepers_of(a.rubric) or []):
        print(f'ОТКАЗ: {a.candidate} уже хранитель рубрики {a.rubric}')
        sys.exit(1)
    used = len(list(year_events('keeper.vouched', voucher=a.voucher)))
    if used >= 2:
        print(f'ОТКАЗ: лимит поручительств — 2 в год (§18.4); у {a.voucher} уже {used}')
        sys.exit(1)
    if not a.text or len(a.text.split()) < 5:
        print('ОТКАЗ: «хороший человек» — не рекомендация; опишите журнальный след кандидата (§18.4)')
        sys.exit(1)
    vid = next_id('v', 'vouch')
    open(os.path.join(TRUST, vid + '.md'), 'w', encoding='utf-8').write(f"""---
id: {vid}
kind: vouch
state: active
candidate: {a.candidate}
rubric: {a.rubric}
voucher: {a.voucher}
created_at: {now()}
---

## Рекомендация

{a.text}
""")
    lid = append_ledger(f'keeper:{a.voucher}', 'keeper.vouched',
                        vouch=vid, candidate=a.candidate, rubric=a.rubric,
                        comment=f'поручительство {used+1}/2 в этом году')
    print(f'{vid}: поручительство {a.voucher} за {a.candidate} ({a.rubric}) записано ({lid}); '
          f'лимит {used+1}/2')


def cmd_appoint(a):
    vs = active_vouches(a.candidate, a.rubric)
    vouchers = sorted({v for v, _ in vs})
    if len(vouchers) < 2:
        print(f'ОТКАЗ: нужно 2 разных поручителя (§18.4), есть {len(vouchers)}: '
              + (', '.join(vouchers) or 'никого'))
        sys.exit(1)
    ks = keepers_of(a.rubric)
    if a.candidate in ks:
        print(f'ОТКАЗ: {a.candidate} уже в списке хранителей {a.rubric}')
        sys.exit(1)
    set_keepers(a.rubric, ks + [a.candidate])
    used_ids = [vid for v, vid in vs if v in vouchers]
    for vid in used_ids:
        p = os.path.join(TRUST, vid + '.md')
        t = open(p, encoding='utf-8').read()
        open(p, 'w', encoding='utf-8').write(t.replace('state: active', 'state: spent', 1))
    lid = append_ledger(f'gardener:{a.gardener}', 'keeper.appointed',
                        keeper=a.candidate, rubric=a.rubric,
                        vouchers=','.join(vouchers),
                        comment='назначение по двум поручительствам (§18.4): ' + ','.join(used_ids))
    print(f'{a.candidate} назначен хранителем {a.rubric} ({lid}); поручители: '
          + ', '.join(vouchers) + '; _rubrics.yml обновлён')


def _recent_recalls(keeper, rubric, days=92):
    out = []
    for l in ledger_lines():
        if 'recall.opened' in l and f'keeper={keeper}' in l and f'rubric={rubric}' in l:
            try:
                d = datetime.date.fromisoformat(l[:10])
            except ValueError:
                continue
            if (TODAY - d).days <= days:
                out.append(l)
    return out


def _initiator_banned(nick):
    """Два recall.dismissed подряд за год → запрет инициации на год (§18.5)."""
    year = str(TODAY.year)
    dismissed = 0
    for l in ledger_lines():
        if not l.startswith(year):
            continue
        if 'recall.dismissed' in l and f'by={nick}' in l.replace('initiator=', 'by='):
            dismissed += 1
        elif 'keeper.recalled' in l and f'initiator={nick}' in l:
            dismissed = 0
    return dismissed >= 2


def cmd_recall_open(a):
    if not a.evidence:
        lid = append_ledger(f'gardener:system', 'recall.rejected',
                            keeper=a.keeper, rubric=a.rubric, initiator=a.by,
                            comment='инициатива без ссылок на факты журнала отклонена (§18.5)')
        print(f'ОТКАЗ: recall требует --evidence ldg-NNNN,... — инициатива отклонена ({lid})')
        sys.exit(1)
    for e in a.evidence.split(','):
        if not any(f'| {e.strip()} |' in l for l in ledger_lines()):
            print(f'ОТКАЗ: записи {e} нет в журнале — recall должен опираться на факты (§18.5)')
            sys.exit(1)
    if _recent_recalls(a.keeper, a.rubric):
        print(f'ОТКАЗ: квота — не чаще одного recall в квартал по хранителю и рубрике (§18.5)')
        sys.exit(1)
    if _initiator_banned(a.by):
        print(f'ОТКАЗ: {a.by} заблокирован на год: два recall.dismissed подряд (§18.5)')
        sys.exit(1)
    rid = next_id('rc', 'recall')
    until = TODAY + datetime.timedelta(days=14)
    open(os.path.join(TRUST, rid + '.md'), 'w', encoding='utf-8').write(f"""---
id: {rid}
kind: recall
state: open
keeper: {a.keeper}
rubric: {a.rubric}
initiator: {a.by}
evidence: [{a.evidence}]
opened_at: {now()}
discussion_until: {until.isoformat()}
---

## Основание

{a.reason}

## Обсуждение

(открыто участникам рубрики до {until.isoformat()}; отвечающая сторона имеет право последнего слова)
""")
    lid = append_ledger(f'author:{a.by}', 'recall.opened',
                        recall=rid, keeper=a.keeper, rubric=a.rubric,
                        evidence=a.evidence,
                        comment=a.reason)
    print(f'{rid}: recall против {a.keeper} ({a.rubric}) открыт ({lid}); '
          f'обсуждение до {until.isoformat()}; кворум решит после')


def cmd_recall_close(a):
    p = os.path.join(TRUST, a.rid + '.md')
    if not os.path.exists(p):
        print(f'ОТКАЗ: нет дела {a.rid}')
        sys.exit(1)
    t = open(p, encoding='utf-8').read()
    if 'state: open' not in t:
        print(f'ОТКАЗ: дело {a.rid} уже закрыто')
        sys.exit(1)
    if not a.reason or len(a.reason.split()) < 8:
        print('ОТКАЗ: итог recall требует полной мотивировки (§18.5): какие факты признаны, какие отклонены')
        sys.exit(1)
    keeper = re.search(r'^keeper: (\S+)', t, re.M).group(1)
    rubric = re.search(r'^rubric: (\S+)', t, re.M).group(1)
    initiator = re.search(r'^initiator: (\S+)', t, re.M).group(1)
    if a.decision == 'recalled':
        ks = keepers_of(rubric)
        if keeper in ks:
            if len(ks) - 1 < 2 and not a.force:
                print(f'ОТКАЗ: снятие оставит рубрику {rubric} с {len(ks)-1} хранителем '
                      f'(красная зона, У1). Сначала назначьте замену или --force.')
                sys.exit(1)
            set_keepers(rubric, [k for k in ks if k != keeper])
            print(f'_rubrics.yml: {keeper} выведен из хранителей {rubric}')
        lid = append_ledger(f'gardener:{a.by}', 'keeper.recalled',
                            recall=a.rid, keeper=keeper, rubric=rubric,
                            quorum=a.quorum, initiator=initiator,
                            comment=a.reason)
    else:
        lid = append_ledger(f'gardener:{a.by}', 'recall.dismissed',
                            recall=a.rid, keeper=keeper, rubric=rubric,
                            quorum=a.quorum, initiator=initiator,
                            comment=a.reason)
    t = t.replace('state: open', 'state: ' + a.decision, 1)
    t += f'\n## Итог ({a.decision})\n\nКворум: {a.quorum}\n\n{a.reason}\n'
    open(p, 'w', encoding='utf-8').write(t)
    print(f'{a.rid}: {a.decision} ({lid}); мотивировка записана в дело и журнал')


def cmd_thanks(a):
    if not a.text or len(a.text.split()) < 4:
        print('ОТКАЗ: благодарность — факт с причиной, а не междометие (§20.7): опишите, за что конкретно')
        sys.exit(1)
    if ':' in a.by:
        actor = a.by
    else:
        actor = ('keeper:' if a.by in all_keepers() else 'author:') + a.by
    lid = append_ledger(actor, 'thanks.recorded', to=a.to, comment=a.text)
    print(f'Благодарность записана ({lid}): {a.to} — видна в журнале и в следе человека (digest.py --person)')


def _rotation(days):
    text = rubrics_text()
    rows = []
    for m in re.finditer(r'- id: (\S+)\n(?:.*\n)*?\s*keepers: \[(.*?)\]', text):
        rubric = m.group(1)
        for k in [x.strip() for x in m.group(2).split(',') if x.strip()]:
            hist = actor_history(k)
            idle = (TODAY - max(hist)).days if hist else 9999
            rows.append((k, rubric, idle))
    return rows


def cmd_rotation_check(a):
    rows = _rotation(a.days)
    bad = [r for r in rows if r[2] >= a.days]
    for k, rubric, idle in rows:
        mark = ' 💤' if idle >= a.days else ''
        print(f'  {k:12s} {rubric:24s} молчит {idle} дн.{mark}')
    print(f'Спящих (>={a.days} дн.): {len(bad)}' + (' — rotation-apply для тихого выхода' if bad else ''))


def cmd_rotation_apply(a):
    rows = _rotation(a.days)
    by_rubric = {}
    for k, rubric, idle in rows:
        by_rubric.setdefault(rubric, []).append((k, idle))
    applied = 0
    for rubric, ks in by_rubric.items():
        cur = keepers_of(rubric)
        for k, idle in ks:
            if idle < a.days:
                continue
            if len(cur) - 1 < 2 and not a.force:
                print(f'  ⚠ {k} ({rubric}): спит {idle} дн., но снятие оставит рубрику '
                      f'с {len(cur)-1} хранителем — пропуск без --force')
                continue
            set_keepers(rubric, [x for x in cur if x != k])
            cur = keepers_of(rubric)
            lid = append_ledger('gardener:system', 'keeper.rotated',
                                keeper=k, rubric=rubric, reason='inactivity',
                                comment=f'тихий выход: {idle} дн. без записей в журнале (§18.3)')
            print(f'  ↺ {k} ({rubric}): тихий выход без позора ({lid})')
            applied += 1
    print(f'Ротация: выведено {applied}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('vouch')
    p.add_argument('candidate'); p.add_argument('--rubric', required=True)
    p.add_argument('--voucher', required=True); p.add_argument('--text', required=True)
    p.set_defaults(f=cmd_vouch)
    p = sub.add_parser('appoint')
    p.add_argument('candidate'); p.add_argument('--rubric', required=True)
    p.add_argument('--gardener', required=True)
    p.set_defaults(f=cmd_appoint)
    p = sub.add_parser('recall')
    sub2 = p.add_subparsers(dest='sub', required=True)
    po = sub2.add_parser('open')
    po.add_argument('keeper'); po.add_argument('--rubric', required=True)
    po.add_argument('--by', required=True); po.add_argument('--reason', required=True)
    po.add_argument('--evidence', default='')
    po.set_defaults(f=cmd_recall_open)
    pc = sub2.add_parser('close')
    pc.add_argument('rid'); pc.add_argument('--decision', choices=['recalled', 'dismissed'], required=True)
    pc.add_argument('--by', required=True); pc.add_argument('--quorum', required=True)
    pc.add_argument('--reason', required=True); pc.add_argument('--force', action='store_true')
    pc.set_defaults(f=cmd_recall_close)
    p = sub.add_parser('thanks')
    p.add_argument('to'); p.add_argument('--by', required=True); p.add_argument('--text', required=True)
    p.set_defaults(f=cmd_thanks)
    p = sub.add_parser('rotation-check'); p.add_argument('--days', type=int, default=90)
    p.set_defaults(f=cmd_rotation_check)
    p = sub.add_parser('rotation-apply'); p.add_argument('--days', type=int, default=90)
    p.add_argument('--force', action='store_true')
    p.set_defaults(f=cmd_rotation_apply)
    a = ap.parse_args()
    a.f(a)


if __name__ == '__main__':
    main()
