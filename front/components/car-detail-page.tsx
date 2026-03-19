"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, apiRequest } from "../lib/api";
import { formatNumber, formatYen } from "../lib/format";
import type { CarDetailResponse } from "../lib/types";


type Props = {
  listingId: string;
};

type DetailEntry = {
  label: string;
  value: string;
};

const orderedFields: DetailEntry[] = [
  { label: "Make", value: "make" },
  { label: "Model", value: "model" },
  { label: "Trim", value: "trim" },
  { label: "Year", value: "year" },
  { label: "Mileage", value: "mileage_km" },
  { label: "Location", value: "location" },
  { label: "Color", value: "color" },
  { label: "Body type", value: "body_type" },
  { label: "Fuel", value: "fuel_type" },
  { label: "Transmission", value: "transmission" },
  { label: "Drive", value: "drive_type" },
  { label: "Engine", value: "engine_volume_cc" },
  { label: "Doors", value: "doors" },
  { label: "Seats", value: "seats" },
  { label: "Inspection", value: "inspection" },
  { label: "Repair history", value: "repair_history" },
  { label: "Maintenance", value: "maintenance" },
  { label: "Guarantee", value: "guarantee" },
  { label: "Shop", value: "shop_name" },
];


export function CarDetailPage({ listingId }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [item, setItem] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activePhoto, setActivePhoto] = useState(0);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const thumbRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const lang = searchParams.get("lang") ?? "en";

  useEffect(() => {
    let cancelled = false;

    apiRequest<CarDetailResponse>(`/cars/${listingId}`, {
      params: { lang },
    })
      .then((payload) => {
        if (!cancelled) {
          setItem(payload.item);
          setActivePhoto(0);
          setDetailsOpen(false);
        }
      })
      .catch((requestError: unknown) => {
        if (!cancelled) {
          if (requestError instanceof ApiError && requestError.status === 401) {
            setError("Session expired.");
            router.replace("/login");
            return;
          }
          if (requestError instanceof ApiError && requestError.status === 404) {
            setError("Car not found.");
            return;
          }
          setError("Could not load the car.");
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
  }, [lang, listingId, router]);

  const photos = useMemo(() => {
    const value = item?.photos;
    return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];
  }, [item]);

  const selectedPhoto = photos[activePhoto] ?? photos[0] ?? null;
  const previewFields = orderedFields.slice(0, 4);

  useEffect(() => {
    const activeThumb = thumbRefs.current[activePhoto];
    activeThumb?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "nearest",
    });
  }, [activePhoto]);

  useEffect(() => {
    if (!detailsOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setDetailsOpen(false);
      }
    }

    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [detailsOpen]);

  function renderValue(field: string, rawValue: unknown): string {
    if (rawValue === null || rawValue === undefined || rawValue === "") {
      return "";
    }
    if (field === "mileage_km") {
      return `${formatNumber(Number(rawValue))} km`;
    }
    if (field === "engine_volume_cc") {
      return `${formatNumber(Number(rawValue))} cc`;
    }
    return String(rawValue);
  }

  return (
    <main className="detail-shell">
      <div className="detail-header">
        <Link href="/inventory">Back to inventory</Link>
        <div className="tag-row">
          <span>ID {listingId}</span>
          <span>Lang {lang}</span>
        </div>
      </div>

      {loading ? <section className="empty-state">Loading car...</section> : null}
      {error ? <section className="empty-state">{error}</section> : null}

      {item && !loading ? (
        <section className="product-layout">
          <section className="product-gallery-panel">
            <div className="product-gallery">
              <div className="product-thumbs-wrap">
                <div className="product-thumbs">
                  {photos.length ? (
                    photos.map((photo, index) => (
                      <button
                        key={photo}
                        className={`thumb-button${index === activePhoto ? " is-active" : ""}`}
                        type="button"
                        onClick={() => setActivePhoto(index)}
                        ref={(node) => {
                          thumbRefs.current[index] = node;
                        }}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={photo} alt={`${String(item.title ?? listingId)} ${index + 1}`} />
                      </button>
                    ))
                  ) : (
                    <div className="thumb-button thumb-placeholder">No photos</div>
                  )}
                </div>
              </div>

              <div className="product-main-image">
                {selectedPhoto ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={selectedPhoto} alt={String(item.title ?? listingId)} />
                ) : (
                  <div className="image-fallback">No photos</div>
                )}
              </div>
            </div>
          </section>

          <section className="product-info-panel">
            <div className="product-copy">
              <p className="eyebrow">{String(item.make ?? "Carsensor")}</p>
              <h1 className="product-title">{String(item.title ?? listingId)}</h1>
              <p className="product-subtitle">
                {String(item.model ?? "")}
                {item.trim ? ` · ${String(item.trim)}` : ""}
              </p>
            </div>

            <div className="tag-row product-tags">
              {typeof item.body_type === "string" ? <span>{item.body_type}</span> : null}
              {typeof item.fuel_type === "string" ? <span>{item.fuel_type}</span> : null}
              {typeof item.transmission === "string" ? <span>{item.transmission}</span> : null}
              {typeof item.drive_type === "string" ? <span>{item.drive_type}</span> : null}
            </div>

            <dl className="product-spec-list">
              {previewFields.map((entry) => {
                const rawValue = item[entry.value];
                const rendered = renderValue(entry.value, rawValue);
                if (!rendered) {
                  return null;
                }

                return (
                  <div key={entry.value} className="product-spec-row">
                    <dt>{entry.label}</dt>
                    <dd>{rendered}</dd>
                  </div>
                );
              })}
            </dl>

            <button className="ghost-button details-trigger" type="button" onClick={() => setDetailsOpen(true)}>
              Show more
            </button>
          </section>

          <aside className="product-aside-panel">
            <div className="price-card">
              <div className="price-block">
                <p className="price-label">Base price</p>
                <p className="price-main">{formatYen(Number(item.base_price_yen ?? 0))}</p>
                {item.total_price_yen ? (
                  <p className="price-secondary">
                    Total: {formatYen(Number(item.total_price_yen))}
                  </p>
                ) : null}
              </div>

              <div className="price-meta">
                {typeof item.year === "number" ? <p>Year: {item.year}</p> : null}
                {typeof item.mileage_km === "number" ? (
                  <p>Mileage: {formatNumber(item.mileage_km)} km</p>
                ) : null}
                {typeof item.location === "string" ? <p>Location: {item.location}</p> : null}
              </div>

              {typeof item.url === "string" ? (
                <a className="primary-button detail-link" href={item.url} target="_blank" rel="noreferrer">
                  Open source listing
                </a>
              ) : null}
            </div>
          </aside>
        </section>
      ) : null}

      {item && detailsOpen ? (
        <div className="details-overlay" onClick={() => setDetailsOpen(false)}>
          <aside
            className="details-drawer"
            onClick={(event) => event.stopPropagation()}
            aria-modal="true"
            role="dialog"
          >
            <div className="details-drawer-head">
              <h2>Specifications</h2>
              <button className="drawer-close" type="button" onClick={() => setDetailsOpen(false)}>
                x
              </button>
            </div>

            <div className="details-drawer-body">
              <dl className="product-spec-list drawer-spec-list">
                {orderedFields.map((entry) => {
                  const rawValue = item[entry.value];
                  const rendered = renderValue(entry.value, rawValue);
                  if (!rendered) {
                    return null;
                  }

                  return (
                    <div key={entry.value} className="product-spec-row">
                      <dt>{entry.label}</dt>
                      <dd>{rendered}</dd>
                    </div>
                  );
                })}
              </dl>
            </div>

            <div className="details-drawer-foot">
              <p className="price-main">{formatYen(Number(item.base_price_yen ?? 0))}</p>
              {typeof item.url === "string" ? (
                <a className="primary-button detail-link" href={item.url} target="_blank" rel="noreferrer">
                  Open source listing
                </a>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}
    </main>
  );
}
