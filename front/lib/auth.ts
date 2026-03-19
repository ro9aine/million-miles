export const TOKEN_STORAGE_KEY = "million-miles-token";
export const LANG_STORAGE_KEY = "million-miles-lang";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

export function getStoredLanguage(): "ja" | "en" | "ru" {
  if (typeof window === "undefined") {
    return "en";
  }
  const value = window.localStorage.getItem(LANG_STORAGE_KEY);
  return value === "ja" || value === "en" || value === "ru" ? value : "en";
}

export function setStoredLanguage(lang: "ja" | "en" | "ru"): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(LANG_STORAGE_KEY, lang);
}
