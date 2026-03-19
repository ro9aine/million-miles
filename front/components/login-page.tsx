"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest } from "../lib/api";
import { setStoredToken, getStoredToken } from "../lib/auth";
import type { LoginResponse } from "../lib/types";


export function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (getStoredToken()) {
      router.replace("/inventory");
    }
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError(null);

    try {
      const response = await apiRequest<LoginResponse>("/auth/login", {
        method: "POST",
        body: { username, password },
      });
      setStoredToken(response.access_token);
      router.replace("/inventory");
    } catch (requestError) {
      setError("Login failed. Use admin / admin123.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel">
        <p className="eyebrow">Million Miles</p>
        <h1>Dealer dashboard</h1>
        <p className="lead">
          JWT login for the imported Carsensor inventory. Default credentials are
          {" "}
          <strong>admin / admin123</strong>.
        </p>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            <span>Login</span>
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </label>

          <label>
            <span>Password</span>
            <input
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>

          {error ? <p className="form-error">{error}</p> : null}

          <button className="primary-button" type="submit" disabled={pending}>
            {pending ? "Signing in..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
