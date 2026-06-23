# Product Classification Management System

Готовое к продакшену REST API и SPA-фронтенд для управления
иерархическим каталогом товаров с настраиваемыми параметрами,
хозяйственными операциями (ХО), аналитикой, журналом аудита и
ролевым доступом.

---

## Возможности

| Раздел | Описание |
|------|---------|
| **Каталог** | Многоуровневое дерево категорий, drag-and-drop сортировка, карточки товаров |
| **Параметры** | Числовые и enum-атрибуты с ограничениями min/max; наследование по дереву категорий |
| **Поиск** | Поиск товаров по нескольким параметрам сразу, по всему поддереву категорий |
| **Хозяйственные операции** | Иерархический классификатор ХО; жизненный цикл draft → posted / cancelled |
| **Dashboard** | Сводные счётчики (категории, товары, параметры, экземпляры ХО) |
| **Аналитика** | Распределение товаров, средняя цена, использование параметров, динамика ХО по месяцам — графики на Chart.js |
| **Авторизация** | JWT-вход (логин + пароль), роли admin / user |
| **Аудит** | Журнал изменений на каждое создание / редактирование / удаление / проведение / отмену |
| **Пользователи** | Админ-панель: создание пользователей, смена роли/пароля, блокировка/активация |
| **Экспорт** | Экспорт в CSV в один клик, с UTF-8 BOM (открывается в Excel без проблем с кодировкой) |

---

## Архитектура

```
Браузер (SPA)  ──JWT──►  FastAPI  ──SQLAlchemy──►  PostgreSQL
    │                        │                          │
index.html              main.py + routers          init.sql  (схема, PL/pgSQL, сид-данные)
vanilla JS              auth / catalog / xo        alembic/  (app_user, audit_log)
Chart.js                export / audit / users     seed_demo_data.py  (демо-данные)
```

![Диаграмма архитектуры](docs/architecture.svg)

### Ключевые архитектурные решения

**Двухуровневое управление схемой** — `init.sql` отвечает за бизнес-схему
(категории, товары, параметры, ХО, PL/pgSQL-функции для проверки циклов,
валидации ролей и т.д.) и применяется один раз, автоматически, образом
`postgres` при первом запуске контейнера. Alembic отвечает только за две
таблицы, добавленные позже (`app_user` и `audit_log`), и применяется
через `alembic upgrade head`. Это позволяет не переписывать PL/pgSQL в
виде Alembic DDL, сохраняя при этом отслеживание миграций.

**`entrypoint.sh` управляет запуском контейнера** — внутри Docker-образа
`app` команды `alembic upgrade head` и `seed_demo_data.py` выполняются
автоматически перед стартом `uvicorn`. Оба шага идемпотентны, поэтому
перезапуск контейнера никогда не дублирует данные.

**Страховка через `create_all`** — `main.py` также вызывает
`Base.metadata.create_all` при старте, поэтому сервер запускается без
ошибок даже там, где Alembic не был вызван (например, при быстром
локальном тесте).

**`audit_log.py` — изолированный хелпер** — `log_action()` коммитит
свою собственную мини-транзакцию. Сбой при записи аудита (таблицы нет,
проблема с сетью) логирует предупреждение и завершается — он никогда не
откатывает уже закоммиченную бизнес-операцию вызывающего кода.

**JWT с fallback на переменные окружения** — `_authenticate_user()`
сначала проверяет таблицу `app_user`; если её ещё нет, происходит
fallback на `ADMIN_USERNAME` / `ADMIN_PASSWORD` из `.env`, поэтому в
только что развёрнутую систему можно зайти ещё до применения миграций.

---

## Стек технологий

| Уровень | Технология |
|-------|-----------|
| Runtime | Python 3.11+ |
| API-фреймворк | FastAPI 0.115 |
| ORM | SQLAlchemy 2.0 |
| База данных | PostgreSQL 15 |
| Миграции | Alembic 1.14 |
| Авторизация | python-jose (JWT · HS256) + bcrypt 4.x (напрямую, без passlib) |
| Фронтенд | Vanilla JS SPA — один файл `index.html`, Chart.js 4.4 |
| Контейнеризация | Docker + docker-compose |

> Фронтенд раздаётся FastAPI как статический файл (`GET /ui`) — без
> сборки, без Node.js.

---

## Быстрый старт — Docker (рекомендуется)

```bash
git clone https://github.com/ваш-логин/product-catalog-manager.git
cd product-catalog-manager
cp .env.example .env
docker-compose up --build
```

Это всё — одна команда. При первом запуске контейнер `app` автоматически:

1. дожидается готовности PostgreSQL,
2. выполняет `alembic upgrade head` (создаёт `app_user` / `audit_log`),
3. выполняет `seed_demo_data.py` (создаёт демо-пользователей + примеры ХО + пример истории аудита),
4. запускает `uvicorn`.

При повторных перезапусках все три шага пропускаются, если данные уже есть.

- **SPA:** http://localhost:8000/ui
- **Swagger:** http://localhost:8000/docs
- **Вход:** `admin` / `admin123` (полный список демо-аккаунтов ниже)

| Логин | Пароль | Роль |
|----------|----------|------|
| `admin` | `admin123` | admin |
| `manager` | `manager123` | user |
| `analyst` | `analyst123` | user |

> `docker-compose.yml` читает `DB_PASSWORD` из `.env` для установки
> пароля PostgreSQL (по умолчанию `securepassword`, если не задан). Это
> отдельная переменная от `DATABASE_URL` — контейнер `app` игнорирует
> значение `DATABASE_URL` из `.env` и использует собственную строку
> подключения к сервису `db`.

---

## Установка без Docker (для локальной разработки)

Этот путь — если вы хотите запускать `uvicorn --reload` напрямую в своём
Python-окружении.

### 1 · Клонирование

```bash
git clone https://github.com/ваш-логин/product-catalog-manager.git
cd product-catalog-manager
```

### 2 · Настройка переменных окружения

```bash
cp .env.example .env
# Отредактируйте .env — как минимум смените SECRET_KEY
```

### 3 · Запуск PostgreSQL

**Вариант A — Postgres в Docker, приложение запускается локально (гибридный, удобный):**
```bash
docker-compose up -d db
```
При первом запуске `init.sql` применяется автоматически — **не
запускайте** его вручную ещё раз: повторный прогон на уже
инициализированной базе завершится ошибками «relation already exists».

**Вариант B — Postgres установлен локально:**
```sql
CREATE USER appuser WITH PASSWORD 'ваш_пароль';
CREATE DATABASE product_catalog OWNER appuser;
GRANT ALL PRIVILEGES ON DATABASE product_catalog TO appuser;
GRANT ALL ON SCHEMA public TO appuser;
```
Затем примените схему самостоятельно:
```bash
psql -h localhost -U appuser -d product_catalog -f init.sql
```

### 4 · Применение миграций Alembic

```bash
# из корня проекта — команда работает из любой директории
alembic upgrade head
```

### 5 · Установка зависимостей и запуск

```bash
pip install -r requirements.txt
cd app
uvicorn main:app --reload
```

- **SPA:** http://localhost:8000/ui
- **Swagger:** http://localhost:8000/docs
- **Админ по умолчанию:** `admin` / `admin123` (из `.env`)

### 6 · Заполнение демо-данными (опционально)

Создаёт демо-аккаунты (`manager`, `analyst`), 13 примеров экземпляров ХО,
распределённых по последним 6 месяцам (чтобы график аналитики не был
пустым/плоским), и 19 реалистичных записей аудита:

```bash
cd app
python seed_demo_data.py
```

Безопасно перезапускать — скрипт сначала проверяет наличие данных и
пропускает то, что уже заполнено.

---

## Запуск тестов

Установите зависимости для тестирования:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Unit-тесты (SQLite, Postgres не требуется)

```bash
pytest -v -m "not integration"
```

Покрывают: JWT-авторизацию, ролевой доступ, CRUD пользователей, смену
паролей, деактивацию аккаунтов, фильтрацию и пагинацию журнала аудита,
статистику dashboard, граничные случаи валидации. **34 теста**, ~10 секунд.

### Интеграционные тесты (требуется Postgres + init.sql)

```bash
docker-compose up -d db
alembic upgrade head

export TEST_DATABASE_URL=postgresql://appuser:securepassword@localhost:5432/product_catalog
pytest -v -m integration
```

Покрывают: CRUD категорий (защита от циклов, защита через FK), CRUD
товаров (аудит изменения цены), полный жизненный цикл ХО (создание →
изменение → проведение → отмена), кодировку CSV-экспорта (UTF-8 BOM),
эндпоинт аналитики. **21 тест**.

### Полный набор

```bash
pytest -v   # unit + integration (integration пропускаются без TEST_DATABASE_URL)
```

CI запускает полный набор автоматически при каждом push через
`.github/workflows/tests.yml`.

---

## Продакшен-развёртывание (systemd)

```ini
# /etc/systemd/system/product-catalog.service
[Unit]
Description=Product Catalog Manager
After=network.target postgresql.service

[Service]
WorkingDirectory=/opt/product-catalog/app
EnvironmentFile=/opt/product-catalog/.env
ExecStart=/opt/product-catalog/.venv/bin/uvicorn main:app \
          --host 0.0.0.0 --port 8000 --workers 2
Restart=on-failure
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable --now product-catalog
```

> `ExecStart` запускает только `uvicorn` — в отличие от Docker-образа,
> здесь **не** выполняется `entrypoint.sh`. Примените `alembic upgrade head`
> (и опционально `seed_demo_data.py`) вручную один раз перед первым запуском.

---

## Документация API

Интерактивный Swagger UI: **`/docs`** — ReDoc: **`/redoc`**

| Эндпоинт | Описание |
|----------|-------------|
| `POST /auth/login` | Получить JWT-токен |
| `GET /auth/me` | Информация о текущем пользователе |
| `GET /api/dashboard/stats` | Счётчики для dashboard |
| `GET /api/analytics` | Агрегированные данные для графиков |
| `GET /api/categories/tree/full` | Полное дерево категорий |
| `GET /api/products/{product_id}` | Детали товара |
| `GET /api/params/search` | Поиск товаров по параметрам |
| `GET /api/xo/instances` | Список экземпляров ХО |
| `GET /api/export/products` | CSV-экспорт (товары) |
| `GET /api/export/xo-instances` | CSV-экспорт (экземпляры ХО) |
| `GET /api/audit/` | Журнал аудита — только admin |
| `GET /api/users/` | Список пользователей — только admin |

Также существует эндпоинт `GET /health` для healthcheck контейнера. Он
намеренно скрыт из схемы Swagger и из логов запросов.

---

## Скриншоты

![Каталог](docs/screenshots/01_catalog.png)
![Dashboard](docs/screenshots/02_dashboard.png)
![Аналитика](docs/screenshots/03_analytics.png)
![Хоз операции](docs/screenshots/04_xo.png)
![Аудит](docs/screenshots/05_audit.png)
![Swagger](docs/screenshots/06_swagger.png)

---

## Лицензия

MIT
