# Million Miles

## Backend

Install Python dependencies, then run the FastAPI app:

```bash
pip install -e .
uvicorn back.main:app --reload
```

The API health endpoint is available at `http://localhost:8000/health`.

## CarSensor CLI

Run the live parser against Carsensor result or detail pages:

```bash
pip install -e .
carsensor-parse --limit 3
```

Translate field content in the output:

```bash
carsensor-parse --limit 1 --lang en
carsensor-parse --limit 1 --lang ru
```

Parse a specific detail page:

```bash
carsensor-parse --url https://www.carsensor.net/usedcar/detail/AU6897426683/index.html
```

Write JSON to a file:

```bash
carsensor-parse --limit 10 --output carsensor.json
```

Use the parser from Python:

```python
from parser import CarSensorParser

parser = CarSensorParser()
listings = parser.crawl(max_pages=1, max_listings=3)
```

## Frontend

Install frontend dependencies inside `front/`, then start Next.js:

```bash
cd front
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` if the backend is not running on `http://localhost:8000`.
