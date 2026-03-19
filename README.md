# Million Miles

Test fullstack application for importing cars from `carsensor.net`, storing them in SQLite, exposing them through FastAPI, and browsing them in Next.js.

## Implemented

- live `CarSensorParser` based on `requests` and `BeautifulSoup`
- field content localization to `ja`, `en`, `ru`
- SQLite storage
- JWT auth with `admin / admin123`
- FastAPI backend:
  - `POST /auth/login`
  - `GET /cars`
  - `GET /cars/{listing_id}`
  - `POST /sync`
  - `GET /sync/meta`
- Celery worker for scraping
- Celery Beat watchdog schedule
- database update immediately after each parsed car record
- Next.js frontend:
  - login page
  - inventory list
  - filters, sorting, pagination
  - detail page
  - language switcher

## Backend

Install dependencies:

```bash
poetry install
```

Run API:

```bash
poetry run back-dev
```

By default backend:

- initializes SQLite at `back/data/million_miles.db`
- creates user `admin / admin123`
- if `STARTUP_SYNC_ENABLED=1`, enqueues immediate sync-check task into Celery

Environment variables:

```bash
JWT_SECRET=change-me
CORS_ORIGIN=http://localhost:3000
AUTH_COOKIE_SECURE=true
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0
SYNC_INTERVAL_SECONDS=3600
SYNC_MAX_PAGES=2
SYNC_MAX_LISTINGS=40
STARTUP_SYNC_ENABLED=1
DATABASE_PATH=back/data/million_miles.db
```

Healthcheck:

```bash
http://localhost:8000/health
```

## Celery

Redis is required as broker/backend.

Example local Redis with Docker:

```bash
docker run --name million-miles-redis -p 6379:6379 redis:7
```

Run worker:

```bash
poetry run back-worker
```

Run beat:

```bash
poetry run back-beat
```

`beat` checks once per minute whether a new sync is due. A sync starts immediately on startup, then the next one becomes eligible only after `SYNC_INTERVAL_SECONDS` have passed since the previous sync finished. `worker` updates the database immediately after every parsed car.

Manual sync is also available through:

```bash
POST /sync
```

## Frontend

Create `front/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Run frontend:

```bash
cd front
npm install
npm run dev
```

The app will be available at `http://localhost:3000`.

## Full Local Run

Terminal 1:

```bash
poetry run back-dev
```

Terminal 2:

```bash
poetry run back-worker
```

Terminal 3:

```bash
poetry run back-beat
```

Terminal 4:

```bash
cd front
npm run dev
```

## Docker Compose

Full stack with Redis, API, Celery worker, Celery beat, and frontend:

```bash
docker compose up --build
```

Compose overrides can be supplied through a root `.env` file. The included
[`deploy.env.example`](./deploy.env.example) shows the required values for a plain HTTP
server deployment:

```bash
cp deploy.env.example .env
docker compose up -d --build
```

Relevant compose variables:

```bash
CORS_ORIGIN=http://your-server:3000
NEXT_PUBLIC_API_URL=http://your-server:8000
AUTH_COOKIE_SECURE=false
STARTUP_SYNC_ENABLED=1
SYNC_INTERVAL_SECONDS=3600
```

Set `AUTH_COOKIE_SECURE=false` only when serving over plain HTTP. For HTTPS deployments,
keep it `true`.

Services:

- frontend: `http://localhost:3000`
- api: `http://localhost:8000`
- redis: `localhost:6379`

Stop:

```bash
docker compose down
```

Reset containers and named volumes:

```bash
docker compose down -v
```

## Parser CLI

```bash
poetry run carsensor-parse --limit 3
poetry run carsensor-parse --limit 1 --lang en
poetry run carsensor-parse --url https://www.carsensor.net/usedcar/detail/AU6897426683/index.html --lang ru
```

## Auth

- login: `admin`
- password: `admin123`

## Localization And Filtering

- scraper keeps canonical source data
- backend stores Japanese source plus localized `en/ru` payloads
- filtering and sorting work on normalized keys and numeric columns
- frontend requests localized content with `lang=ja|en|ru`
