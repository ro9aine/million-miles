from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag

try:
    from deep_translator import GoogleTranslator
except ImportError:  # pragma: no cover - optional until dependencies are installed
    GoogleTranslator = None


BASE_URL = "https://www.carsensor.net"
DEFAULT_SEARCH_URL = f"{BASE_URL}/usedcar/index.html?NEW=1&SORT=19"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)

DETAIL_ID_RE = re.compile(r"/usedcar/detail/([A-Z0-9]+)/index\.html")
PRICE_RE = re.compile(r"setting_data\.price\s*=\s*'(\d+),(\d+)'")
YEAR_RE = re.compile(r"(\d{4})")
SUPPORTED_LANGS = ("ja", "en", "ru")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

DETAIL_LABELS = {
    "body_type": ["ボディタイプ"],
    "drive_type": ["駆動方式"],
    "color": ["色"],
    "transmission": ["ミッション"],
    "engine_volume": ["排気量"],
    "seats": ["乗車定員"],
    "doors": ["ドア数"],
    "fuel_type": ["使用燃料", "エンジン種別"],
    "inspection": ["車検有無"],
    "repair_history": ["修復歴"],
    "maintenance": ["法定整備"],
    "guarantee": ["保証"],
    "year": ["年式(初度登録年)", "年式"],
    "mileage": ["走行距離"],
}


@dataclass(slots=True)
class CarListing:
    listing_id: str | None = None
    make: str | None = None
    model: str | None = None
    trim: str | None = None
    title: str | None = None
    year: int | None = None
    mileage_km: int | None = None
    base_price_yen: int | None = None
    total_price_yen: int | None = None
    currency: str = "JPY"
    url: str | None = None
    location: str | None = None
    color: str | None = None
    body_type: str | None = None
    fuel_type: str | None = None
    transmission: str | None = None
    drive_type: str | None = None
    engine_volume_cc: int | None = None
    doors: int | None = None
    seats: int | None = None
    inspection: str | None = None
    repair_history: str | None = None
    maintenance: str | None = None
    guarantee: str | None = None
    shop_name: str | None = None
    shop_url: str | None = None
    photos: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_localized_dict(self, lang: str = "ja") -> dict[str, Any]:
        translator = ContentTranslator(lang=lang)
        return translator.translate_payload(self.to_dict())


@dataclass(slots=True)
class ListingPreview:
    url: str
    make: str | None = None
    title: str | None = None
    base_price_yen: int | None = None
    total_price_yen: int | None = None
    year: int | None = None
    mileage_km: int | None = None
    image_url: str | None = None
    shop_name: str | None = None
    shop_url: str | None = None


class CarSensorParser:
    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            }
        )

    def crawl(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int = 1,
        max_listings: int | None = None,
    ) -> list[CarListing]:
        return list(
            self.iter_listings(
                start_url=start_url,
                max_pages=max_pages,
                max_listings=max_listings,
            )
        )

    def iter_listings(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int = 1,
        max_listings: int | None = None,
    ):
        seen_listing_urls: set[str] = set()
        current_url = start_url
        pages_fetched = 0
        yielded = 0

        while current_url and pages_fetched < max_pages:
            html = self._fetch_html(current_url)
            previews, next_url = self.parse_result_page(html, base_url=current_url)
            pages_fetched += 1

            for preview in previews:
                if preview.url in seen_listing_urls:
                    continue
                seen_listing_urls.add(preview.url)
                yield self.fetch_listing(preview.url, preview=preview)
                yielded += 1
                if max_listings is not None and yielded >= max_listings:
                    return

            current_url = next_url

    def fetch_listing(self, url: str, preview: ListingPreview | None = None) -> CarListing:
        html = self._fetch_html(url)
        return self.parse_detail_page(html, url=url, preview=preview)

    def parse_result_page(self, html: str, base_url: str = BASE_URL) -> tuple[list[ListingPreview], str | None]:
        soup = BeautifulSoup(html, "html.parser")
        previews: list[ListingPreview] = []
        seen_urls: set[str] = set()

        for link in soup.select("a[href]"):
            href = link.get("href", "")
            if not DETAIL_ID_RE.search(href):
                continue

            url = urljoin(base_url, href)
            if url in seen_urls:
                continue
            seen_urls.add(url)

            cassette = link.find_parent(class_=re.compile(r"cassette"))
            image = cassette.select_one("img") if isinstance(cassette, Tag) else link.select_one("img")
            shop_link = cassette.select_one("a[href*='/shop/']") if isinstance(cassette, Tag) else None

            previews.append(
                ListingPreview(
                    url=url,
                    title=self._clean_value(self._attr_or_none(image, "alt")),
                    image_url=self._normalize_image_url(self._attr_or_none(image, "data-original") or self._attr_or_none(image, "src")),
                    shop_name=self._text_or_none(shop_link),
                    shop_url=urljoin(base_url, shop_link.get("href", "")) if isinstance(shop_link, Tag) else None,
                )
            )

        return previews, self._extract_next_page_url(soup, base_url)

    def parse_detail_page(self, html: str, url: str, preview: ListingPreview | None = None) -> CarListing:
        soup = BeautifulSoup(html, "html.parser")
        title_node = soup.select_one("h1.title1")
        title_text = self._text_or_none(title_node)
        title_parts = self._split_title(title_text)
        table_values = self._extract_table_values(soup)
        product = self._extract_product_ld_json(soup)
        listing_id = self._extract_listing_id(url)
        base_price_yen, total_price_yen = self._extract_prices(html, soup, preview, product)
        photo_urls = self._extract_photo_urls(soup, product)
        shop_name, shop_url = self._extract_shop(product, preview)

        listing = CarListing(
            listing_id=listing_id,
            make=title_parts["make"] or self._preview_or_none(preview, "make") or self._extract_brand(product, 0),
            model=title_parts["model"] or self._extract_brand(product, 1),
            trim=title_parts["trim"],
            title=title_text or self._preview_or_none(preview, "title") or self._json_get(product, "name"),
            year=self._parse_year(self._lookup_detail_value(table_values, "year")) or self._preview_or_none(preview, "year"),
            mileage_km=self._parse_mileage_km(self._lookup_detail_value(table_values, "mileage")) or self._preview_or_none(preview, "mileage_km"),
            base_price_yen=base_price_yen,
            total_price_yen=total_price_yen,
            url=url,
            location=self._extract_location(soup, product),
            color=self._clean_value(self._lookup_detail_value(table_values, "color")) or self._json_get(product, "color"),
            body_type=self._clean_value(self._lookup_detail_value(table_values, "body_type")),
            fuel_type=self._clean_value(self._lookup_detail_value(table_values, "fuel_type")),
            transmission=self._clean_value(self._lookup_detail_value(table_values, "transmission")),
            drive_type=self._clean_value(self._lookup_detail_value(table_values, "drive_type")),
            engine_volume_cc=self._parse_engine_volume_cc(self._lookup_detail_value(table_values, "engine_volume")),
            doors=self._parse_int(self._lookup_detail_value(table_values, "doors")),
            seats=self._parse_int(self._lookup_detail_value(table_values, "seats")),
            inspection=self._clean_value(self._lookup_detail_value(table_values, "inspection")),
            repair_history=self._clean_value(self._lookup_detail_value(table_values, "repair_history")),
            maintenance=self._clean_value(self._lookup_detail_value(table_values, "maintenance")),
            guarantee=self._clean_value(self._lookup_detail_value(table_values, "guarantee")),
            shop_name=shop_name,
            shop_url=shop_url,
            photos=photo_urls,
            raw={
                "table_values": table_values,
                "product": product,
            },
        )

        return listing

    def _fetch_html(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        if "carsensor.net" in response.url:
            response.encoding = "utf-8"
        else:
            response.encoding = response.encoding or response.apparent_encoding or "utf-8"
        return response.text

    def _extract_next_page_url(self, soup: BeautifulSoup, base_url: str) -> str | None:
        candidates = soup.select("a[rel='next'], a.pager__next, a.next, a[aria-label='次へ']")
        for candidate in candidates:
            href = candidate.get("href")
            if href:
                return urljoin(base_url, href)

        for candidate in soup.select("a[href]"):
            href = candidate.get("href", "")
            if "/usedcar/" in href and ("page=" in href.lower() or "pg=" in href.lower()):
                return urljoin(base_url, href)
        return None

    def _extract_table_values(self, soup: BeautifulSoup) -> dict[str, str]:
        values: dict[str, str] = {}
        for row in soup.select("tr"):
            heads = row.select("th.defaultTable__head")
            descriptions = row.select("td.defaultTable__description")
            for head, description in zip(heads, descriptions, strict=False):
                key = self._text_or_none(head)
                value = self._text_or_none(description)
                if key and value:
                    values[self._clean_key(key)] = self._clean_value(value) or ""

        if "年式" not in values or "走行距離" not in values:
            for title, value in zip(soup.select(".specWrap__box__title"), soup.select(".specWrap__box__text"), strict=False):
                key = self._clean_key(self._text_or_none(title) or "")
                cleaned = self._clean_value(self._text_or_none(value))
                if key and cleaned:
                    values[key] = cleaned

        return values

    def _lookup_detail_value(self, values: dict[str, str], field_name: str) -> str | None:
        for label in DETAIL_LABELS[field_name]:
            value = values.get(label)
            if value:
                return value
        return None

    def _extract_product_ld_json(self, soup: BeautifulSoup) -> dict[str, Any]:
        for script in soup.select("script[type='application/ld+json']"):
            text = script.string or script.get_text()
            if not text.strip():
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            product = self._find_product_node(payload)
            if product:
                return product
        return {}

    def _find_product_node(self, payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            if payload.get("@type") == "Product":
                return payload
            for value in payload.values():
                found = self._find_product_node(value)
                if found:
                    return found
        elif isinstance(payload, list):
            for item in payload:
                found = self._find_product_node(item)
                if found:
                    return found
        return None

    def _extract_prices(
        self,
        html: str,
        soup: BeautifulSoup,
        preview: ListingPreview | None,
        product: dict[str, Any],
    ) -> tuple[int | None, int | None]:
        match = PRICE_RE.search(html)
        if match:
            return int(match.group(1)), int(match.group(2))

        base_price = self._parse_price_to_yen(self._text_or_none(soup.select_one(".basePrice__price")))
        total_price = self._parse_price_to_yen(self._text_or_none(soup.select_one(".totalPrice__price")))

        if base_price is None:
            base_price = self._preview_or_none(preview, "base_price_yen") or self._parse_int(self._json_get_nested(product, ["offers", 0, "price"]))
        if total_price is None:
            total_price = self._preview_or_none(preview, "total_price_yen")

        return base_price, total_price

    def _extract_photo_urls(self, soup: BeautifulSoup, product: dict[str, Any]) -> list[str]:
        urls: list[str] = []

        for node in soup.select("a.js-photo"):
            url = node.get("data-photohq") or node.get("data-photo")
            normalized = self._normalize_image_url(url)
            if normalized:
                urls.append(normalized)

        product_image = self._normalize_image_url(self._json_get(product, "image"))
        if product_image:
            urls.append(product_image)

        seen: set[str] = set()
        result: list[str] = []
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            result.append(url)
        return result

    def _extract_shop(self, product: dict[str, Any], preview: ListingPreview | None) -> tuple[str | None, str | None]:
        seller = self._json_get_nested(product, ["offers", 0, "seller"]) or {}
        shop_name = self._json_get(seller, "name") or self._preview_or_none(preview, "shop_name")
        shop_url = self._json_get(seller, "url") or self._preview_or_none(preview, "shop_url")
        return self._clean_value(shop_name), shop_url

    def _extract_location(self, soup: BeautifulSoup, product: dict[str, Any]) -> str | None:
        title = self._text_or_none(soup.select_one("title")) or ""
        if "(" in title and ")" in title:
            location = title.split("(", 1)[1].split(")", 1)[0]
            if location:
                return location

        breadcrumbs = [self._text_or_none(node) for node in soup.select(".breadcrumb li")]
        breadcrumbs = [item for item in breadcrumbs if item]
        if len(breadcrumbs) >= 2:
            maybe_location = breadcrumbs[-2]
            if "中古車" in maybe_location:
                return maybe_location.replace("の中古車", "").replace("・", " ").strip()

        seller_url = self._json_get_nested(product, ["offers", 0, "seller", "url"]) or ""
        if "/shop/" in seller_url:
            parts = seller_url.split("/shop/", 1)[-1].split("/")
            if parts:
                return parts[0]
        return None

    def _extract_brand(self, product: dict[str, Any], index: int) -> str | None:
        brands = self._json_get(product, "brand")
        if isinstance(brands, list) and len(brands) > index:
            brand = brands[index]
            if isinstance(brand, dict):
                return self._json_get(brand, "name")
            if isinstance(brand, str):
                return brand
        return None

    def _extract_listing_id(self, url: str) -> str | None:
        match = DETAIL_ID_RE.search(url)
        return match.group(1) if match else None

    def _split_title(self, title: str | None) -> dict[str, str | None]:
        if not title:
            return {"make": None, "model": None, "trim": None}

        head = title.replace("\xa0", " ").split("（", 1)[0].strip()
        parts = [part for part in head.split(" ") if part]
        if len(parts) < 2:
            return {"make": head, "model": None, "trim": None}

        return {
            "make": parts[0],
            "model": parts[1],
            "trim": " ".join(parts[2:]) or None,
        }

    def _parse_price_to_yen(self, value: str | None) -> int | None:
        if not value:
            return None

        normalized = value.replace(",", "").replace(" ", "")
        if "万円" in normalized:
            number = normalized.split("万円", 1)[0]
            try:
                return int(round(float(number) * 10_000))
            except ValueError:
                return None

        digits = "".join(ch for ch in normalized if ch.isdigit())
        return int(digits) if digits else None

    def _parse_mileage_km(self, value: str | None) -> int | None:
        if not value:
            return None

        normalized = value.replace(",", "").replace(" ", "")
        if "万km" in normalized:
            number = normalized.split("万km", 1)[0]
            try:
                return int(round(float(number) * 10_000))
            except ValueError:
                return None

        digits = "".join(ch for ch in normalized if ch.isdigit())
        return int(digits) if digits else None

    def _parse_year(self, value: str | None) -> int | None:
        if not value:
            return None
        match = YEAR_RE.search(value)
        return int(match.group(1)) if match else None

    def _parse_engine_volume_cc(self, value: str | None) -> int | None:
        if not value:
            return None

        normalized = value.replace(",", "").replace(" ", "")
        if "cc" in normalized.lower():
            digits = "".join(ch for ch in normalized if ch.isdigit())
            return int(digits) if digits else None
        if "L" in normalized:
            try:
                return int(round(float(normalized.split("L", 1)[0]) * 1000))
            except ValueError:
                return None
        return self._parse_int(normalized)

    def _parse_int(self, value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            digits = "".join(ch for ch in value if ch.isdigit())
            return int(digits) if digits else None
        return None

    def _clean_key(self, value: str) -> str:
        return re.sub(r"\s+", "", value.replace("\xa0", " ")).strip()

    def _clean_value(self, value: str | None) -> str | None:
        if not value:
            return None
        cleaned = re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()
        return cleaned or None

    def _normalize_image_url(self, url: str | None) -> str | None:
        if not url:
            return None
        cleaned = url.strip()
        duplicate_index = cleaned.find("https://", 8)
        if duplicate_index > 0:
            cleaned = cleaned[duplicate_index:]
        duplicate_http_index = cleaned.find("http://", 7)
        if duplicate_http_index > 0:
            cleaned = cleaned[duplicate_http_index:]
        if cleaned.startswith("//"):
            return f"https:{cleaned}"
        if cleaned.startswith("/"):
            return urljoin(BASE_URL, cleaned)
        if cleaned.startswith("http"):
            return cleaned
        return None

    def _attr_or_none(self, node: Tag | None, attr: str) -> str | None:
        if not isinstance(node, Tag):
            return None
        value = node.get(attr)
        return value if isinstance(value, str) else None

    def _text_or_none(self, node: Any) -> str | None:
        if isinstance(node, Tag):
            return node.get_text(" ", strip=True)
        return None

    def _json_get(self, payload: dict[str, Any], key: str) -> Any:
        value = payload.get(key)
        return value

    def _json_get_nested(self, payload: Any, path: list[Any]) -> Any:
        current = payload
        for key in path:
            if isinstance(key, int) and isinstance(current, list) and len(current) > key:
                current = current[key]
            elif isinstance(key, str) and isinstance(current, dict):
                current = current.get(key)
            else:
                return None
        return current

    def _preview_or_none(self, preview: ListingPreview | None, attr: str) -> Any:
        return getattr(preview, attr, None) if preview else None


class ContentTranslator:
    def __init__(self, lang: str = "ja") -> None:
        if lang not in SUPPORTED_LANGS:
            raise ValueError(f"Unsupported language: {lang}")
        self.lang = lang

    def translate_payload(self, payload: Any) -> Any:
        if self.lang == "ja":
            return payload

        if isinstance(payload, dict):
            return {key: self.translate_payload(value) for key, value in payload.items()}

        if isinstance(payload, list):
            return [self.translate_payload(item) for item in payload]

        if isinstance(payload, str):
            return self._translate_string(payload)

        return payload

    def _translate_string(self, value: str) -> str:
        if not value.strip():
            return value
        if URL_RE.match(value):
            return value
        return _translate_text(value, self.lang)


@lru_cache(maxsize=2048)
def _translate_text(text: str, lang: str) -> str:
    if lang == "ja":
        return text

    if GoogleTranslator is None:
        raise RuntimeError(
            "Content translation requires 'deep-translator'. Install project dependencies first."
        )

    return GoogleTranslator(source="ja", target=lang).translate(text)


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live Carsensor parser CLI.")
    parser.add_argument(
        "--url",
        default=DEFAULT_SEARCH_URL,
        help="Result page URL to crawl or detail page URL to parse.",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="How many result pages to crawl.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Maximum number of listings to return.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write JSON output.",
    )
    parser.add_argument(
        "--lang",
        choices=SUPPORTED_LANGS,
        default="ja",
        help="Translate string field content to the target language at output time.",
    )
    return parser


def main() -> None:
    args = build_cli_parser().parse_args()
    carsensor = CarSensorParser(timeout=args.timeout)

    if DETAIL_ID_RE.search(args.url):
        listings = [carsensor.fetch_listing(args.url)]
    else:
        listings = carsensor.crawl(
            start_url=args.url,
            max_pages=args.pages,
            max_listings=args.limit,
        )

    payload = [listing.to_localized_dict(lang=args.lang) for listing in listings]
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(args.output)
        return

    print(rendered)
