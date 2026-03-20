from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import Any, AsyncIterator
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, Tag

from parser.models import CarListing, ListingPreview, PreviewPageResult

try:
    from deep_translator import GoogleTranslator
except ImportError:  # pragma: no cover - optional until dependencies are installed
    GoogleTranslator = None


BASE_URL = "https://www.carsensor.net"
DEFAULT_SEARCH_URL = f"{BASE_URL}/usedcar/index.html"
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
RESULT_PAGE_RE = re.compile(r"/usedcar/index(\d+)\.html(?:[?#].*)?$", re.IGNORECASE)
logger = logging.getLogger(__name__)

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


class ParserFetchError(RuntimeError):
    pass


class CarSensorParser:
    def __init__(
        self,
        timeout: int = 30,
        preview_batch_size: int = 10,
        request_concurrency: int = 10,
    ) -> None:
        self.timeout = timeout
        self.preview_batch_size = max(1, preview_batch_size)
        self.request_concurrency = max(1, request_concurrency)
        self.headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        }

    async def crawl(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int | None = 1,
        max_listings: int | None = None,
    ) -> list[CarListing]:
        logger.info(
            "Starting crawl start_url=%s max_pages=%s max_listings=%s preview_batch_size=%s",
            start_url,
            max_pages,
            max_listings,
            self.preview_batch_size,
        )
        listings: list[CarListing] = []
        async for listing in self.iter_listings(
            start_url=start_url,
            max_pages=max_pages,
            max_listings=max_listings,
        ):
            listings.append(listing)
        return listings

    async def iter_listings(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int | None = 1,
        max_listings: int | None = None,
    ) -> AsyncIterator[CarListing]:
        yielded = 0
        async for preview_batch in self.iter_preview_batches(start_url=start_url, max_pages=max_pages):
            batch = preview_batch
            if max_listings is not None:
                remaining = max_listings - yielded
                if remaining <= 0:
                    return
                batch = batch[:remaining]

            for preview, listing, error in await self.fetch_listings_with_status(batch):
                if error is not None:
                    raise error
                if listing is None:
                    raise ParserFetchError(f"Listing fetch returned no result for {preview.url}")
                yielded += 1
                logger.info("Yielded listing count=%s listing_id=%s", yielded, listing.listing_id)
                yield listing

                if max_listings is not None and yielded >= max_listings:
                    return

    async def iter_previews(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int | None = 1,
    ) -> AsyncIterator[ListingPreview]:
        async for batch in self.iter_preview_batches(start_url=start_url, max_pages=max_pages):
            for preview in batch:
                yield preview

    async def iter_preview_page_batches(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int | None = 1,
    ) -> AsyncIterator[list[PreviewPageResult]]:
        start_page = self._extract_result_page_number(start_url)
        pages_remaining = max_pages
        next_page = start_page

        async with self._session() as session:
            while pages_remaining is None or pages_remaining > 0:
                batch_size = self.preview_batch_size if pages_remaining is None else min(
                    self.preview_batch_size, pages_remaining)
                page_numbers = list(range(next_page, next_page + batch_size))
                logger.info("Fetching preview batch page_numbers=%s", page_numbers)
                batch_results = await self._fetch_preview_batch(session, page_numbers)

                yielded_results: list[PreviewPageResult] = []
                for page_result in batch_results:
                    current_page_count = len(page_result.previews)
                    logger.info(
                        "Parsed preview page page_number=%s previews=%s error=%s",
                        page_result.page_number,
                        current_page_count,
                        page_result.error,
                    )
                    yielded_results.append(page_result)

                if not any(page_result.previews for page_result in yielded_results):
                    logger.info(
                        "Stopping preview collection because batch returned no previews page_numbers=%s",
                        page_numbers,
                    )
                    break

                yield yielded_results

                next_page += batch_size
                if pages_remaining is not None:
                    pages_remaining -= batch_size

    async def iter_preview_batches(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int | None = 1,
    ) -> AsyncIterator[list[ListingPreview]]:
        seen_listing_urls: set[str] = set()
        async for page_results in self.iter_preview_page_batches(start_url=start_url, max_pages=max_pages):
            collected_batch: list[ListingPreview] = []
            for page_result in page_results:
                for preview in page_result.previews:
                    if preview.url in seen_listing_urls:
                        logger.debug("Skipping duplicate preview url=%s", preview.url)
                        continue
                    seen_listing_urls.add(preview.url)
                    collected_batch.append(preview)

            logger.info("Collected preview batch unique_count=%s", len(collected_batch))
            if not collected_batch:
                continue
            yield collected_batch

    async def collect_previews(
        self,
        start_url: str = DEFAULT_SEARCH_URL,
        max_pages: int | None = 1,
    ) -> list[ListingPreview]:
        collected: list[ListingPreview] = []
        async for batch in self.iter_preview_batches(start_url=start_url, max_pages=max_pages):
            collected.extend(batch)
        logger.info("Collected previews total=%s", len(collected))
        return collected

    async def fetch_listing(self, url: str, preview: ListingPreview | None = None) -> CarListing:
        async with self._session() as session:
            return await self._fetch_listing_async(session, url, preview=preview)

    async def fetch_listings(self, previews: list[ListingPreview]) -> list[CarListing]:
        results = await self.fetch_listings_with_status(previews)
        listings: list[CarListing] = []
        for preview, listing, error in results:
            if error is not None:
                raise error
            if listing is None:
                raise ParserFetchError(f"Listing fetch returned no result for {preview.url}")
            listings.append(listing)
        return listings

    async def fetch_listings_with_status(
        self,
        previews: list[ListingPreview],
    ) -> list[tuple[ListingPreview, CarListing | None, Exception | None]]:
        async with self._session() as session:
            async def worker(preview: ListingPreview) -> tuple[ListingPreview, CarListing | None, Exception | None]:
                try:
                    listing = await self._fetch_listing_async(session, preview.url, preview=preview)
                    return (preview, listing, None)
                except Exception as exc:
                    return (preview, None, exc)

            return await asyncio.gather(*(worker(preview) for preview in previews))

    async def fetch_preview_pages(self, page_numbers: list[int]) -> list[PreviewPageResult]:
        async with self._session() as session:
            return await self._fetch_preview_batch(session, page_numbers)

    async def _fetch_preview_batch(
        self,
        session: aiohttp.ClientSession,
        page_numbers: list[int],
    ) -> list[PreviewPageResult]:
        async def worker(page_number: int) -> PreviewPageResult:
            url = self._build_result_page_url(page_number)
            logger.info("Fetching result page page_number=%s url=%s", page_number, url)
            try:
                html = await self._fetch_html_async(session, url)
            except ParserFetchError:
                logger.warning("Failed to fetch preview page page_number=%s url=%s", page_number, url, exc_info=True)
                return PreviewPageResult(
                    page_number=page_number,
                    url=url,
                    error=f"Failed to fetch {url}",
                )

            previews = self.parse_result_page(html, base_url=url)
            return PreviewPageResult(page_number=page_number, url=url, previews=previews)

        results = await asyncio.gather(*(worker(page_number) for page_number in page_numbers))
        return sorted(results, key=lambda item: item.page_number)

    async def _fetch_listing_async(
        self,
        session: aiohttp.ClientSession,
        url: str,
        preview: ListingPreview | None = None,
    ) -> CarListing:
        logger.info(
            "Fetching listing detail url=%s listing_id=%s",
            url,
            preview.listing_id if preview else None,
        )
        html = await self._fetch_html_async(session, url)
        listing = self.parse_detail_page(html, url=url, preview=preview)
        logger.info("Parsed listing detail listing_id=%s url=%s", listing.listing_id, url)
        return listing

    def extract_listing_id(self, url: str) -> str | None:
        return self._extract_listing_id(url)

    def build_result_page_url(self, page_number: int) -> str:
        return self._build_result_page_url(page_number)

    def parse_result_page(self, html: str, base_url: str = BASE_URL) -> list[ListingPreview]:
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
                    listing_id=self._extract_listing_id(url),
                    url=url,
                    title=self._clean_value(self._attr_or_none(image, "alt")),
                    image_url=self._normalize_image_url(
                        self._attr_or_none(image, "data-original") or self._attr_or_none(image, "src")
                    ),
                    shop_name=self._text_or_none(shop_link),
                    shop_url=urljoin(base_url, shop_link.get("href", "")) if isinstance(shop_link, Tag) else None,
                )
            )

        logger.info(
            "Extracted previews from result page base_url=%s count=%s",
            base_url,
            len(previews),
        )
        return previews

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

        return CarListing(
            listing_id=listing_id,
            make=title_parts["make"] or self._preview_or_none(preview, "make") or self._extract_brand(product, 0),
            model=title_parts["model"] or self._extract_brand(product, 1),
            trim=title_parts["trim"],
            title=title_text or self._preview_or_none(preview, "title") or self._json_get(product, "name"),
            year=self._parse_year(self._lookup_detail_value(table_values, "year")
                                  ) or self._preview_or_none(preview, "year"),
            mileage_km=self._parse_mileage_km(self._lookup_detail_value(table_values, "mileage"))
            or self._preview_or_none(preview, "mileage_km"),
            base_price_yen=base_price_yen,
            total_price_yen=total_price_yen,
            url=url,
            location=self._extract_location(soup, product),
            color=self._clean_value(self._lookup_detail_value(table_values, "color")
                                    ) or self._json_get(product, "color"),
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

    async def _fetch_html_async(self, session: aiohttp.ClientSession, url: str) -> str:
        logger.info("Requesting url=%s", url)
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                raw_body = await response.read()
                final_url = str(response.url)
                if "carsensor.net" in final_url:
                    text = raw_body.decode("utf-8", errors="replace")
                else:
                    charset = response.charset or "utf-8"
                    text = raw_body.decode(charset, errors="replace")
                logger.info(
                    "Received response url=%s status_code=%s final_url=%s",
                    url,
                    response.status,
                    final_url,
                )
                return text
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise ParserFetchError(f"Failed to fetch {url}") from exc

    def _session(self) -> aiohttp.ClientSession:
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        return aiohttp.ClientSession(
            headers=self.headers,
            timeout=timeout,
            connector=aiohttp.TCPConnector(limit=self.request_concurrency),
        )

    def _extract_result_page_number(self, url: str) -> int:
        lowered_url = url.lower()
        if "/usedcar/index.html" in lowered_url:
            return 1

        match = RESULT_PAGE_RE.search(url)
        if match:
            return int(match.group(1))

        return 0

    def _build_result_page_url(self, page_number: int) -> str:
        if page_number <= 1:
            return DEFAULT_SEARCH_URL
        return f"{BASE_URL}/usedcar/index{page_number}.html"

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
            base_price = self._preview_or_none(preview, "base_price_yen") or self._parse_int(
                self._json_get_nested(product, ["offers", 0, "price"])
            )
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
        return payload.get(key)

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
