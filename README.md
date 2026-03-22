# API-сервис сокращения ссылок



**POST** /links/shorten – создает короткую ссылку, доп. параметры - custom_alias, expires_at.  

Пример запроса:
```json
{
  "original_url": "https://example.com/",
  "custom_alias": "string",
  "expires_at": "2026-03-15T19:50:33.725Z"
}
```
Пример ответа:
```json
{
  "data": {
    "short_code": "string",
    "short_url": "http://127.0.0.1:8000/links/string",
    "original_url": "https://example.com/",
    "expires_at": "2026-03-15T19:56:19.139000+00:00"
  }
}
```
**GET** /links/{short_code} – перенаправляет на оригинальный URL.  

Параметр:
- `short_code` — короткая ссылка;

При переходе:
- увеличивается `click_count`;
- обновляется `last_used_at`;

**DELETE** /links/{short_code} – удаляет связь.  

- `short_code` — короткая ссылка;

Пример ответа:
```json
{
  "data": "Link 9961S7 deleted"
}
```
**PUT** /links/{short_code} – обновляет URL.

Параметр: 
- `short_code` — новая короткая ссылка;

Пример запроса:
```json
{
  "original_url": "https://example.com/"
}
```

Пример ответа:
```json
{
  "data": {
    "short_code": "abc123",
    "new_original_url": "https://new-example.com/"
  }
}
```
**GET** /links/{short_code}/stats - статистика по ссылке: оригинальный URL, дата создания, количество переходов, дата последнего использовани.  

Параметр:
- `short_code` — короткая ссылка;

Пример ответа:

```json
{
  "data": {
    "original_url": "https://example.com/",
    "short_code": "abc123",
    "created_at": "2026-03-14T18:57:06.828619+00:00",
    "click_count": 5,
    "last_used_at": "2026-03-14T20:10:00+00:00",
    "expires_at": "2026-12-31T23:59:59+00:00"
  }
}
```
**GET** /links/search?original_url={url} - поиск ссылки по оригинальному URL.  

Параметр:
- `original_url` — оригинальный URL;

Пример ответа:
```json
{
  "data": [
    {
      "id": 1,
      "original_url": "https://example.com/",
      "short_code": "abc123"
    }
  ]
}
```

**POST** /auth/register - cоздаёт нового пользователя.  
```json
{
  "email": "test@example.com",
  "password": "string",
  "is_active": true,
  "is_superuser": false,
  "is_verified": false
}
```
**POST** /auth/jwt/login - выполняет вход пользователя и возвращает JWT-токен.

Параметры передаются как form-data:
- `username` — email пользователя;
- `password` — пароль.



## Инструкция по запуску

### Запуск через Docker Compose

1. Убедиться, что файл `.env` содержит необходимые переменные окружения.

2. Запустить проект:

```bash
docker compose up --build
```

3. После запуска будут доступны:
- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`

---
## Описание базы данных


### Таблица `user`


Поля:
- `id` — идентификатор пользователя;
- `email` — адрес электронной почты;
- `hashed_password` — хеш пароля;
- `is_active` — активность аккаунта;
- `is_superuser` — признак администратора;
- `is_verified` — подтверждение аккаунта.

---

### Таблица `links`


Поля:
- `id` — первичный ключ;
- `original_url` — исходный URL;
- `short_code` — уникальный короткий код;
- `owner_id` — идентификатор владельца ссылки;
- `click_count` — количество переходов;
- `created_at` — дата создания;
- `last_used_at` — дата последнего использования;
- `expires_at` — срок действия ссылки.

---
## Тесты

### Юнит-тесты

#### Реализованы:

- unit-тесты для проверки вспомогательной логики и отдельных веток обработки
- функциональные API-тесты с использованием `pytest` и `httpx`
- нагрузочное тестирование с использованием `Locust`

Тесты находятся в папке tests/ на одном уровне с src/.

#### Для запуска тестов: 

Зависимости:

```bash
pip install pytest pytest-asyncio pytest-mock httpx coverage locust
```

Запуск тестов:

Нужен файл .coveragerc со следующим содержанием:
```bash
[coverage:run]
concurrency = greenlet, thread
```

Без него не считалось покрытие API-тестов.

```bash
PYTHONPATH=src pytest tests -v
PYTHONPATH=src coverage run --source=src -m pytest tests
coverage report -m
```

Уже готовый html отчет находится в `htmlcov/index.html`

### Нагрузочное тестирование

Поднять проект:

```bash
docker compose up -d --build
```

Закинуть в бд несколько коротких ссылок:

```bash
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/1","custom_alias":"abc123"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/2","custom_alias":"def456"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/3","custom_alias":"ghi789"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/4","custom_alias":"jkl012"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/5","custom_alias":"mno345"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/6","custom_alias":"pqr678"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/7","custom_alias":"stu901"}'

curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url":"https://example.com/8","custom_alias":"vwx234"}'
```

Запустить Locust:

```bash
locust -f locustfile.py --host=http://localhost:8000
```

Тестирование проводилось двумя запусками, первый - с предварительно очищенным кэшем Redis, второй без очищения кэша.

```bash
docker exec -it shortener-redis redis-cli FLUSHALL
locust -f locustfiles.py --host=http://localhost:8000 --users 100 --spawn-rate 20 --run-time 1m
```

#### Отчеты по тестированию:
 - Locust_1_locustfile.py_http___localhost_8000.html
 - Locust_2_locustfile.py_http___localhost_8000.html

#### Вывод:

Во втором прогоне наблюдается улучшение почти по всем ключевым метрикам. Для GET /links/{short_code} среднее время ответа снизилось с 50.04 мс до 45.12 мс, а 95-й перцентиль — со 110 мс до 91 мс. Для GET /links/{short_code}/stats среднее время ответа снизилось с 35.11 мс до 31.53 мс, а 95-й перцентиль — с 91 мс до 79 мс. Общая пропускная способность также выросла: с 1994.82 RPS до 2189.87 RPS. Можно сделать вывод, что кэширование положительно влияет на производительность.