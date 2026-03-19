from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from parser import CarSensorParser
from parser.carsensor import DEFAULT_SEARCH_URL, DETAIL_ID_RE, SUPPORTED_LANGS


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
        "--preview-batch-size",
        type=int,
        default=10,
        help="How many result pages to fetch concurrently per preview batch.",
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    carsensor = CarSensorParser(
        timeout=args.timeout,
        preview_batch_size=args.preview_batch_size,
    )

    if DETAIL_ID_RE.search(args.url):
        listing = asyncio.run(carsensor.fetch_listing(args.url))
        payload = [listing.to_localized_dict(lang=args.lang)]
    else:
        listings = asyncio.run(
            carsensor.crawl(
                start_url=args.url,
                max_pages=args.pages,
                max_listings=args.limit,
            )
        )
        payload = [listing.to_localized_dict(lang=args.lang) for listing in listings]

    rendered = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
        print(args.output)
        return

    print(rendered)
