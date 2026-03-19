export const LANG_STORAGE_KEY = "million-miles-lang";

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
