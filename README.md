# info90

Репозиторий о формах организации информации в сети: от чатов и форумов до вики, каталогов и ИИ-диалогов — их история, плюсы, минусы и проект идеальной гибридной формы.

## 📂 Содержимое

### 📚 [zhivaya-biblioteka/](zhivaya-biblioteka/) — проект «Живая Библиотека»

Концепция идеальной формы организации информации, собранной из лучших сторон всех исторических форм с устранением их минусов: **«GitHub для знаний», скрещённый с Википедией и форумом**. Комплект из 18 документов:

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

**Три главных правила проекта:** поток не хранит знания · у каждого утверждения есть дата и хранитель · человек публикует, машина помогает.

### ⚙️ [prototype/](prototype/) — рабочий прототип (фазы 0–3 + поток)

Концепция в коде, без зависимостей — только Python 3.8+:

- [build.py](prototype/build.py) — генератор сайта: канон → HTML + RSS + журнал + здоровье + черновики
- [propose_change.py](prototype/propose_change.py) / [review_change.py](prototype/review_change.py) — PR-модель правок: дифф, accept/return, обязательный комментарий ревью
- [check_freshness.py](prototype/check_freshness.py) — сканер здоровья канона (метрики, exit-коды для CI, заявки хранителям rq-NNNN)
- [ask.py](prototype/ask.py) — **RAG-навигатор**: отвечает только цитатами карточек с версиями и датами; вне канона честно молчит
- [distill.py](prototype/distill.py) — **ИИ-дистилляция**: тред чата → черновик карточки в [inbox/](prototype/inbox/) (машина черновит, человек публикует)
- [export.py](prototype/export.py) — **экспорт-зеркало**: полный снапшот в tar.gz + sha256-манифест
- [federate.py](prototype/federate.py) — **федерация**: карточки → ActivityPub Article, outbox по рубрикам
- [deadman.py](prototype/deadman.py) — **dead man's switch**: молчание инстанса >N дней → публикация канона на зеркала из [_mirrors.yml](prototype/_mirrors.yml)
- [migrate.py](prototype/migrate.py) — **амнистия-миграция**: архив внешнего сообщества → черновики (демо: форум oldweb-forum.ru → kn-2026-0419/0420)
- [question.py](prototype/question.py) — **вопросы как объект**: закрываются только ссылкой на карточку; open-вопросы = backlog рубрик ([questions/](prototype/questions/))
- [thread.py](prototype/thread.py) — **потоковый слой**: реплики, сигнал «полезно» (не вердикт), кнопка «📌 в канон» ([threads/](prototype/threads/))
- [digest.py](prototype/digest.py) — **еженедельный дайджест-смотр** хранителей ([digest/](prototype/digest/))
- [ci-freshness.yml](prototype/ci-freshness.yml) — шаблон workflow: еженедельный cron-сканер + deadman-алерт
- [_rubrics.yml](prototype/_rubrics.yml) — рубрики со **списками хранителей** (≥2 на рубрику, защита от захвата — угроза У1); все зоны здоровья зелёные
- [_ledger.log](prototype/_ledger.log) — публичный журнал власти (append-only, 17 событий)
- [canon/](prototype/canon/) — 3 карточки; [kn-2026-0007](prototype/canon/formy/katalogi/kn-2026-0007-katalogi.md) прошла полный цикл ревизии (v8 → v9 через заявку [ch-0001](prototype/changes/ch-0001.md)); заявка [ch-0002](prototype/changes/ch-0002.md) **возвращена** хранителем — канон не изменился
- [dist/](prototype/dist/) — собранный сайт: канон, журнал власти, здоровье, черновики, RSS-фиды, федерация

Железное правило (документ 10 §10.4): у ИИ-пайплайна нет write-доступа к канону — только чтение и черновики-заявки.

### 📰 [index.html](index.html) — тестовая страница

Тестовая страница-дайджест: новости ИИ, нейросетей и компьютерных технологий (все материалы — учебные примеры для проверки вёрстки).

---

*Материалы подготовлены при участии ИИ-ассистента · Июль 2026*
