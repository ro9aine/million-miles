# Million Miles

## Backend

Install Python dependencies, then run the FastAPI app:

```bash
pip install -e .
uvicorn back.main:app --reload
```

The API health endpoint is available at `http://localhost:8000/health`.

## Frontend

Install frontend dependencies inside `front/`, then start Next.js:

```bash
cd front
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_URL` if the backend is not running on `http://localhost:8000`.
