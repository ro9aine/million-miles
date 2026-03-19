"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, apiRequest } from "../lib/api";
import {
  clearStoredToken,
  getStoredLanguage,
  getStoredToken,
  setStoredLanguage,
} from "../lib/auth";
import { formatNumber, formatYen } from "../lib/format";
import type { CarListResponse, Lang, SyncResponse } from "../lib/types";


type FiltersState = {
  query: string;
  make: string;
  body_type: string;
  fuel_type: string;
  transmission: string;
  drive_type: string;
  location: string;
  min_year: string;
  max_year: string;
  min_price: string;
  max_price: string;
  min_mileage: string;
  max_mileage: string;
  sort_by: "synced_at" | "price" | "year" | "mileage";
  sort_order: "asc" | "desc";
};

type RangeFilterKey =
  | "min_year"
  | "max_year"
  | "min_price"
  | "max_price"
  | "min_mileage"
  | "max_mileage";

const defaultFilters: FiltersState = {
  query: "",
  make: "",
  body_type: "",
  fuel_type: "",
  transmission: "",
  drive_type: "",
  location: "",
  min_year: "",
  max_year: "",
  min_price: "",
  max_price: "",
  min_mileage: "",
  max_mileage: "",
  sort_by: "synced_at",
  sort_order: "desc",
};

const YEAR_MIN = 1900;
const YEAR_MAX = 2100;
const NON_NEGATIVE_MIN = 0;
const YEAR_STEP = 1;
const PRICE_STEP = 10000;
const MILEAGE_STEP = 1000;

function clampNumber(value: number, min: number, max?: number): number {
  const upperBound = max ?? Number.POSITIVE_INFINITY;
  return Math.min(Math.max(value, min), upperBound);
}

function normalizeNumericString(value: string, min: number, max?: number): string {
  if (value === "") {
    return "";
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return "";
  }

  return String(clampNumber(Math.trunc(parsed), min, max));
}

function normalizeFilters(filters: FiltersState): FiltersState {
  const normalized: FiltersState = {
    ...filters,
    min_year: normalizeNumericString(filters.min_year, YEAR_MIN, YEAR_MAX),
    max_year: normalizeNumericString(filters.max_year, YEAR_MIN, YEAR_MAX),
    min_price: normalizeNumericString(filters.min_price, NON_NEGATIVE_MIN),
    max_price: normalizeNumericString(filters.max_price, NON_NEGATIVE_MIN),
    min_mileage: normalizeNumericString(filters.min_mileage, NON_NEGATIVE_MIN),
    max_mileage: normalizeNumericString(filters.max_mileage, NON_NEGATIVE_MIN),
  };

  const rangePairs: Array<[RangeFilterKey, RangeFilterKey]> = [
    ["min_year", "max_year"],
    ["min_price", "max_price"],
    ["min_mileage", "max_mileage"],
  ];

  for (const [minKey, maxKey] of rangePairs) {
    const minValue = normalized[minKey];
    const maxValue = normalized[maxKey];
    if (minValue === "" || maxValue === "") {
      continue;
    }
    if (Number(minValue) > Number(maxValue)) {
      normalized[maxKey] = minValue;
    }
  }

  return normalized;
}

function getRequestErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) {
      return "One or more filters are outside the API limits.";
    }
    return `Request failed (${error.status}).`;
  }
  return "Could not load inventory. Check API availability.";
}


export function InventoryPage() {
  const router = useRouter();
  const [token, setToken] = useState<string | null>(null);
  const [lang, setLang] = useState<Lang>("en");
  const [filters, setFilters] = useState<FiltersState>(defaultFilters);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<CarListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [syncPending, setSyncPending] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    const storedToken = getStoredToken();
    if (!storedToken) {
      router.replace("/login");
      return;
    }
    setToken(storedToken);
    setLang(getStoredLanguage());
  }, [router]);

  useEffect(() => {
    if (!token) {
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    apiRequest<CarListResponse>("/cars", {
      token,
      params: {
        lang,
        page,
        page_size: 12,
        ...normalizeFilters(filters),
      },
    })
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          if (requestError instanceof ApiError && requestError.status === 401) {
            clearStoredToken();
            setError("Session expired.");
            router.replace("/login");
            return;
          }
          setError(getRequestErrorMessage(requestError));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [filters, lang, page, router, token]);

  useEffect(() => {
    if (!filtersOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setFiltersOpen(false);
      }
    }

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [filtersOpen]);

  function handleLogout() {
    clearStoredToken();
    router.replace("/login");
  }

  function updateFilter(key: keyof FiltersState, value: string) {
    setPage(1);
    setFilters((current) => normalizeFilters({ ...current, [key]: value }));
  }

  function handleLanguageChange(value: Lang) {
    setStoredLanguage(value);
    setLang(value);
  }

  async function handleForceSync() {
    if (!token || syncPending) {
      return;
    }

    setSyncPending(true);
    setSyncMessage(null);
    setError(null);

    try {
      const response = await apiRequest<SyncResponse>("/sync", {
        token,
        method: "POST",
      });
      setSyncMessage(response.queued ? `Sync queued: ${response.task_id}` : "Sync request was not queued.");
      setPage(1);
    } catch (requestError: unknown) {
      if (requestError instanceof ApiError && requestError.status === 401) {
        clearStoredToken();
        setError("Session expired.");
        router.replace("/login");
        return;
      }
      setSyncMessage(null);
      setError(getRequestErrorMessage(requestError));
    } finally {
      setSyncPending(false);
    }
  }

  function renderFilterControls() {
    return (
      <div className="filters-grid">
        <select className="control" value={filters.make} onChange={(event) => updateFilter("make", event.target.value)}>
          <option value="">All makes</option>
          {data?.available_filters.makes.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select className="control" value={filters.body_type} onChange={(event) => updateFilter("body_type", event.target.value)}>
          <option value="">All body types</option>
          {data?.available_filters.body_types.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select className="control" value={filters.fuel_type} onChange={(event) => updateFilter("fuel_type", event.target.value)}>
          <option value="">All fuel types</option>
          {data?.available_filters.fuel_types.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select className="control" value={filters.transmission} onChange={(event) => updateFilter("transmission", event.target.value)}>
          <option value="">All transmissions</option>
          {data?.available_filters.transmissions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select className="control" value={filters.drive_type} onChange={(event) => updateFilter("drive_type", event.target.value)}>
          <option value="">All drive types</option>
          {data?.available_filters.drive_types.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select className="control" value={filters.location} onChange={(event) => updateFilter("location", event.target.value)}>
          <option value="">All locations</option>
          {data?.available_filters.locations.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        <select className="control" value={filters.sort_by} onChange={(event) => updateFilter("sort_by", event.target.value)}>
          <option value="synced_at">Newest sync</option>
          <option value="price">Price</option>
          <option value="year">Year</option>
          <option value="mileage">Mileage</option>
        </select>

        <select className="control" value={filters.sort_order} onChange={(event) => updateFilter("sort_order", event.target.value)}>
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>

        <input className="control" type="number" min={YEAR_MIN} max={YEAR_MAX} step={YEAR_STEP} placeholder="Min year" value={filters.min_year} onChange={(event) => updateFilter("min_year", event.target.value)} />
        <input className="control" type="number" min={YEAR_MIN} max={YEAR_MAX} step={YEAR_STEP} placeholder="Max year" value={filters.max_year} onChange={(event) => updateFilter("max_year", event.target.value)} />
        <input className="control" type="number" min={NON_NEGATIVE_MIN} step={PRICE_STEP} placeholder="Min price" value={filters.min_price} onChange={(event) => updateFilter("min_price", event.target.value)} />
        <input className="control" type="number" min={NON_NEGATIVE_MIN} step={PRICE_STEP} placeholder="Max price" value={filters.max_price} onChange={(event) => updateFilter("max_price", event.target.value)} />
        <input className="control" type="number" min={NON_NEGATIVE_MIN} step={MILEAGE_STEP} placeholder="Min mileage" value={filters.min_mileage} onChange={(event) => updateFilter("min_mileage", event.target.value)} />
        <input className="control" type="number" min={NON_NEGATIVE_MIN} step={MILEAGE_STEP} placeholder="Max mileage" value={filters.max_mileage} onChange={(event) => updateFilter("max_mileage", event.target.value)} />
      </div>
    );
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Million Miles</p>
          <h1>Carsensor stock</h1>
        </div>

        <div className="topbar-actions">
          <button className="primary-button" type="button" onClick={handleForceSync} disabled={!token || syncPending}>
            {syncPending ? "Queueing..." : "Force sync"}
          </button>
          <select
            className="control"
            value={lang}
            onChange={(event) => handleLanguageChange(event.target.value as Lang)}
          >
            <option value="en">English</option>
            <option value="ru">Русский</option>
            <option value="ja">日本語</option>
          </select>
          <button className="ghost-button" type="button" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <section className="mobile-search-bar">
        <input
          className="control"
          placeholder="Search by title, make, model"
          value={filters.query}
          onChange={(event) => updateFilter("query", event.target.value)}
        />
        <button className="ghost-button mobile-filter-trigger" type="button" onClick={() => setFiltersOpen(true)}>
          Filters
        </button>
      </section>

      <section className="filters-panel desktop-filters">
        <div className="filters-desktop-top">
          <input
            className="control"
            placeholder="Search by title, make, model"
            value={filters.query}
            onChange={(event) => updateFilter("query", event.target.value)}
          />
        </div>
        {renderFilterControls()}
      </section>

      <section className="results-bar">
        <div>
          <strong>{data?.total ?? 0}</strong> cars in storage
        </div>
        {syncMessage ? <p>{syncMessage}</p> : null}
        {error ? <p className="form-error">{error}</p> : null}
      </section>

      {loading ? (
        <section className="empty-state">Loading inventory...</section>
      ) : data?.items.length ? (
        <section className="cards-grid">
          {data.items.map((car) => (
            <article key={car.listing_id} className="car-card">
              <Link
                className="car-card-link"
                href={`/cars/${car.listing_id}?lang=${lang}`}
                aria-label={`Open ${car.title ?? car.model ?? car.listing_id}`}
              >
                <div className="car-card-media">
                  {car.main_photo ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={car.main_photo} alt={car.title ?? car.listing_id} />
                  ) : (
                    <div className="image-fallback">No photo</div>
                  )}
                </div>
                <div className="car-card-body">
                  <p className="card-kicker">{car.make ?? "Unknown make"}</p>
                  <h2>{car.title ?? car.model ?? car.listing_id}</h2>
                  <p className="card-price">{formatYen(car.base_price_yen)}</p>
                  <div className="spec-row">
                    <span>{car.year ?? "-"}</span>
                    <span>{formatNumber(car.mileage_km)} km</span>
                    <span>{car.location ?? "-"}</span>
                  </div>
                  <div className="tag-row">
                    {car.body_type ? <span>{car.body_type}</span> : null}
                    {car.fuel_type ? <span className="desktop-tag">{car.fuel_type}</span> : null}
                    {car.transmission ? <span className="desktop-tag">{car.transmission}</span> : null}
                  </div>
                  <div className="card-actions">
                    <span>Open details</span>
                    {car.url ? (
                      <a
                        href={car.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(event) => event.stopPropagation()}
                      >
                        Source
                      </a>
                    ) : null}
                  </div>
                </div>
              </Link>
            </article>
          ))}
        </section>
      ) : (
        <section className="empty-state">No cars matched the current filters.</section>
      )}

      <footer className="pager">
        <button
          className="ghost-button"
          type="button"
          disabled={!data || page <= 1}
          onClick={() => setPage((current) => Math.max(1, current - 1))}
        >
          Previous
        </button>
        <span>
          Page {data?.page ?? page} / {data?.total_pages ?? 1}
        </span>
        <button
          className="ghost-button"
          type="button"
          disabled={!data || page >= (data?.total_pages ?? 1)}
          onClick={() => setPage((current) => current + 1)}
        >
          Next
        </button>
      </footer>

      {filtersOpen ? (
        <div className="details-overlay" onClick={() => setFiltersOpen(false)}>
          <aside
            className="details-drawer inventory-filters-drawer"
            onClick={(event) => event.stopPropagation()}
            aria-modal="true"
            role="dialog"
          >
            <div className="details-drawer-head">
              <h2>Filters</h2>
              <button className="drawer-close" type="button" onClick={() => setFiltersOpen(false)}>
                x
              </button>
            </div>
            <div className="details-drawer-body">
              {renderFilterControls()}
            </div>
            <div className="details-drawer-foot">
              <button className="ghost-button" type="button" onClick={() => setFilters(defaultFilters)}>
                Reset
              </button>
              <button className="primary-button" type="button" onClick={() => setFiltersOpen(false)}>
                Apply
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </main>
  );
}
