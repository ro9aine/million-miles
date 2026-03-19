const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

async function getApiStatus(): Promise<string> {
  try {
    const response = await fetch(`${apiBaseUrl}/health`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return `API returned ${response.status}`;
    }

    const payload = (await response.json()) as { status?: string };
    return payload.status === "ok" ? "API is online" : "Unexpected API response";
  } catch {
    return "API is unreachable";
  }
}

export default async function HomePage() {
  const apiStatus = await getApiStatus();

  return (
    <main className="page">
      <section className="panel">
        <p className="eyebrow">Million Miles</p>
        <h1>Next.js frontend is ready.</h1>
        <p className="lead">
          The frontend expects the FastAPI backend at
          {" "}
          <code>{apiBaseUrl}</code>.
        </p>
        <div className="status">
          <span className="status-label">Backend status</span>
          <strong>{apiStatus}</strong>
        </div>
      </section>
    </main>
  );
}
