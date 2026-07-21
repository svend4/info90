# info90

Репозиторий о формах организации информации в сети: от чатов и форумов до вики, каталогов и ИИ-диалогов — их история, плюсы, минусы и проект идеальной гибридной формы.

## 📂 Содержимое

### 📚 [zhivaya-biblioteka/](zhivaya-biblioteka/) — проект «Живая Библиотека»

Концепция идеальной формы организации информации, собранной из лучших сторон всех исторических форм с устранением их минусов: **«GitHub для знаний», скрещённый с Википедией и форумом**. Комплект из 24 документов:

| № | Документ | О чём |
|---|----------|-------|
| — | [README](zhivaya-biblioteka/README.md) | Оглавление и концепция в одном абзаце |
| 01 | [Концепция](zhivaya-biblioteka/01-koncepciya.md) | Из чего собрана форма, 10 принципов |
| 02 | [Архитектура](zhivaya-biblioteka/02-arkhitektura.md) | 7 слоёв системы, объектная модель, потоки |
| 03 | [Жизненный цикл и роли](zhivaya-biblioteka/03-zhiznenny-cikl-i-roli.md) | Путь знания от чата до канона, роли людей |
| 04 | [Доверие и модерация](zhivaya-biblioteka/04-doverie-i-moderaciya.md) | Гибридная модерация, защита от исторических катастроф |
| 05 | [Таблица минусов](zhivaya-biblioteka/05-tablica-minusov.md) | Как убран каждый минус каждой формы |
| 06 | [Интерфейсы](zhivaya-biblioteka/06-interfeysy.md) | Макеты экранов: главная, карточка, правка, ревью, ИИ |
| 07 | [Устав](zhivaya-biblioteka/07-ustav-i-granichnye-sluchai.md) | Конституция и 8 кризисных сценариев |
| 08 | [Экономика и запуск](zhivaya-biblioteka/08-ekonomika-i-zapusk.md) | Смета, дорожная карта, честные риски |
| 09 | [Сравнение](zhivaya-biblioteka/09-sravnenie-s-suschestvuyushimi.md) | Отличия от Википедии, GitHub, Reddit и др. |
| 10 | [Техспецификация](zhivaya-biblioteka/10-tekhnicheskaya-specifikaciya.md) | Форматы данных, REST API, RAG-пайплайн, федерация |
| 11 | [Политики контента](zhivaya-biblioteka/11-politiki-kontenta.md) | Критерии качества, источники, стайлгайд, чек-лист ревью |
| 12 | [Онбординг](zhivaya-biblioteka/12-onbording-i-scenarii.md) | Первые 15 минут новичка, journey-карты ролей |
| 13 | [Метрики и ритуалы](zhivaya-biblioteka/13-metriki-i-ritualy.md) | Панель здоровья системы, анти-метрики |
| 14 | [Миграция и глоссарий](zhivaya-biblioteka/14-migraciya-i-glossarij.md) | Playbook переезда сообщества + словарь терминов |
| 15 | [Вопросы и потоки](zhivaya-biblioteka/15-voprosy-i-potoki.md) | Механика границы «поток ↔ канон»: вопрос как объект, кнопка 📌, сигнал полезности |
| 16 | [Модель угроз](zhivaya-biblioteka/16-model-ugroz.md) | 8 векторов атак с защитой по слоям и остаточными рисками |
| 17 | [Протокол федерации](zhivaya-biblioteka/17-protokol-federacii.md) | Канон федеративен, власть локальна: идентичность роль@инстанс, реплики, зеркала, форки рубрик |
| 18 | [Экономика доверия](zhivaya-biblioteka/18-ekonomika-doveriya.md) | Репутация без чисел: читаемая история, поручительство (vouching), отзыв доверия (recall) |
| 19 | [Глазами читателя](zhivaya-biblioteka/19-glazami-chitatelya.md) | Опыт человека без ролей: пути к знанию, паспорт карточки, подписки без алгоритмов, офлайн и уход |
| 20 | [Годовой цикл](zhivaya-biblioteka/20-godovoj-cikl.md) | Год как единица жизни инстанса: перевыборы (2 срока + перерыв), годовой отчёт, сезонные волны ревизий, ревизия устава, день сада, перепись федерации |
| 21 | [Глазами садовника](zhivaya-biblioteka/21-glazami-sadovnika.md) | Верхняя роль изнутри: неделя садовника, инструменты и запреты, 6 дилемм, выгорание, контроль как комфорт, ≥2 садовника |
| 22 | [Глазами хранителя](zhivaya-biblioteka/22-glazami-khranitelya.md) | Центральная рабочая роль изнутри: ревью как ремесло, неделя хранителя, цена подписи, ≥2 хранителя |
| 23 | [Глазами автора](zhivaya-biblioteka/23-glazami-avtora.md) | Самая массовая роль изнутри: первая правка, ремесло заявки, апелляция, след без чисел, рост в хранители |

**Три главных правила проекта:** поток не хранит знания · у каждого утверждения есть дата и хранитель · человек публикует, машина помогает.

### ⚙️ [prototype/](prototype/) — рабочий прототип (фазы 0–4 + доверие, подписи, годовой контур, апелляции)

Концепция в коде, без зависимостей — только Python 3.8+:

- [build.py](prototype/build.py) — генератор сайта: канон → HTML + RSS + журнал + здоровье + черновики
- [propose_change.py](prototype/propose_change.py) / [review_change.py](prototype/review_change.py) — PR-модель правок: дифф, accept/return, обязательный комментарий ревью, механический отвод (`review_ban`) после вердикта апелляции
- [appeal.py](prototype/appeal.py) — **апелляции на возврат** (документ 04, §22.8, §18.9.4): подаёт только автор, одна на заявку; арбитр — действующий садовник с **механическим отводом** (не может судить собственный возврат или собственную апелляцию); `appeal.filed / appeal.upheld / appeal.rejected` подписаны; upheld возвращает заявку в работу с отводом вернувшего хранителя ([appeals/](prototype/appeals/))
- [check_freshness.py](prototype/check_freshness.py) — сканер здоровья канона (метрики, exit-коды для CI, заявки хранителям rq-NNNN)
- [ask.py](prototype/ask.py) — **RAG-навигатор**: отвечает только цитатами карточек с версиями и датами; вне канона честно молчит
- [distill.py](prototype/distill.py) — **ИИ-дистилляция**: тред чата → черновик карточки в [inbox/](prototype/inbox/) (машина черновит, человек публикует)
- [export.py](prototype/export.py) — **экспорт-зеркало**: полный снапшот в tar.gz + sha256-манифест
- [federate.py](prototype/federate.py) — **федерация**: карточки → ActivityPub Article, outbox по рубрикам
- [deadman.py](prototype/deadman.py) — **dead man's switch**: молчание инстанса >N дней → публикация канона на зеркала из [_mirrors.yml](prototype/_mirrors.yml)
- [migrate.py](prototype/migrate.py) — **амнистия-миграция**: архив внешнего сообщества → черновики (демо: форум oldweb-forum.ru → kn-2026-0419/0420)
- [question.py](prototype/question.py) — **вопросы как объект**: закрываются только ссылкой на карточку; open-вопросы = backlog рубрик ([questions/](prototype/questions/))
- [thread.py](prototype/thread.py) — **потоковый слой**: реплики, сигнал «полезно» (не вердикт), кнопка «📌 в канон» ([threads/](prototype/threads/))
- [digest.py](prototype/digest.py) — **еженедельный дайджест-смотр** + след человека `--person` ([digest/](prototype/digest/))
- [trust.py](prototype/trust.py) — **процедуры доверия** (документ 18): поручительство, назначение, recall, тихая ротация + **благодарности дня сада** (`thanks.recorded`, §20.7) ([trust/](prototype/trust/))
- [sign.py](prototype/sign.py) — **ключи и подписи журнала** (§17.5): HMAC-подпись действий ролей, `verify-ledger` ловит подделку записей; приватные ключи не коммитятся — публичны только отпечатки в [_keys/registry.yml](prototype/_keys/registry.yml)
- [publish.py](prototype/publish.py) — **публикация черновиков**: единственный путь в канон — решение хранителя; `publish` (inbox→canon, подписанное `draft.published`) и `return` с обязательным комментарием (§11.4)
- [election.py](prototype/election.py) — **перевыборы садовников** (§20.3): номинация только с отчётом («нет отчёта, нет власти»), кворум — большинство хранителей ∪ садовников, лимит 2 срока подряд + годичный перерыв, `gardener.elected/retired`; **watch — автотриггер молчания садовника** (§20.9.2): фиксирует только другой садовник, самофиксация запрещена, `gardener.silence` подписано; реестр [_gardeners.yml](prototype/_gardeners.yml), номинации в [elections/](prototype/elections/)
- [annual.py](prototype/annual.py) — **годовой контур** (§20.4–20.8): `report` (годовой отчёт карточкой канона → [kn-2026-0423](prototype/canon/sistema/otchety/kn-2026-0423.md), `report.annual`), `charter` (устав карточкой → [kn-2026-0422](prototype/canon/sistema/ustav/kn-2026-0422.md) v2, отказ при обсуждении <30 дней, `charter.amended`), `census` (перепись зеркал, `federation.census`; после поднятия зеркал — живы 2/0)
- [webapp.py](prototype/webapp.py) — **веб-обёртка поверх CLI**: панель, навигатор, вопросы, заявки, ревью — каждая кнопка вызывает тот же CLI-скрипт; заявка [ch-0003](prototype/changes/ch-0003.md) проведена через веб end-to-end
- [subscribe.py](prototype/subscribe.py) — **подписка на чужие рубрики**: outbox другого инстанса → реплики read-only; конфликт id, удаление не распространяется
- [ci-freshness.yml](prototype/ci-freshness.yml) — шаблон workflow: еженедельный cron-сканер + deadman-алерт
- [_rubrics.yml](prototype/_rubrics.yml) — рубрики со **списками хранителей** (≥2 на рубрику, защита от захвата — угроза У1), включая системную рубрику «Система и власть»; все зоны здоровья зелёные
- [_ledger.log](prototype/_ledger.log) — публичный журнал власти (append-only, **50 событий**; действия ролей подписаны ключами)
- [canon/](prototype/canon/) — **8 карточек**: 3 исходные + 3 опубликованные из черновиков (kn-2026-0418/0419/0420) + устав и годовой отчёт (kn-2026-0422/0423); [kn-2026-0007](prototype/canon/formy/katalogi/kn-2026-0007-katalogi.md) прошла полный цикл ревизии (v8 → v9 через заявку [ch-0001](prototype/changes/ch-0001.md)) и **полный цикл апелляции** (v9 → v10: возврат → [ap-0002](prototype/appeals/ap-0002.md) upheld → принята со-хранителем после отвода); заявка [ch-0002](prototype/changes/ch-0002.md) **возвращена** хранителем, апелляция [ap-0001](prototype/appeals/ap-0001.md) отклонена арбитром — канон не изменился; черновик kn-2026-0421 возвращён с комментарием
- [dist/](prototype/dist/) — собранный сайт: канон, журнал власти (50 событий), здоровье, черновики, RSS-фиды, федерация (8 Articles)

Железное правило (документ 10 §10.4): у ИИ-пайплайна нет write-доступа к канону — только чтение и черновики-заявки.

### 🌐 [prototype-beta/](prototype-beta/) — второй инстанс (демо федерации)

Минимальная вторая библиотека по [документу 17](zhivaya-biblioteka/17-protokol-federacii.md):
свой канон ([kn-2026-1001](prototype-beta/canon/soobshchestva/forumy/kn-2026-1001-zakrytye-forumy.md)),
свои хранители, подписка на рубрики альфы через subscribe.py — реплики read-only в
[replicas/lib-alpha/](prototype-beta/replicas/lib-alpha/) с журналом `_sync.log`
(отработаны сценарии: конфликт id, исчезновение и возвращение оригинала).
Канон федеративен, власть локальна.

### 📰 [index.html](index.html) — тестовая страница

Тестовая страница-дайджест: новости ИИ, нейросетей и компьютерных технологий (все материалы — учебные примеры для проверки вёрстки).

---

*Материалы подготовлены при участии ИИ-ассистента · Июль 2026*
