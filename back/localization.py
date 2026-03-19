from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from deep_translator import GoogleTranslator


SUPPORTED_LANGS = ("ja", "en", "ru")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)

STATIC_TRANSLATIONS: dict[str, dict[str, str]] = {
    "修復歴なし": {"en": "No repair history", "ru": "Без истории ремонта"},
    "修復歴あり": {"en": "Repair history", "ru": "Есть история ремонта"},
    "保証付": {"en": "Warranty included", "ru": "С гарантией"},
    "保証無": {"en": "No warranty", "ru": "Без гарантии"},
    "法定整備付": {"en": "Maintenance included", "ru": "С техобслуживанием"},
    "法定整備無": {"en": "No scheduled maintenance", "ru": "Без техобслуживания"},
    "ガソリン": {"en": "Gasoline", "ru": "Бензин"},
    "ハイブリッド": {"en": "Hybrid", "ru": "Гибрид"},
    "ディーゼル": {"en": "Diesel", "ru": "Дизель"},
    "電気": {"en": "Electric", "ru": "Электро"},
    "AT": {"en": "Automatic", "ru": "Автомат"},
    "MT": {"en": "Manual", "ru": "Механика"},
    "CVT": {"en": "CVT", "ru": "Вариатор"},
    "FF": {"en": "FWD", "ru": "Передний привод"},
    "4WD": {"en": "4WD", "ru": "Полный привод"},
    "AWD": {"en": "AWD", "ru": "Полный привод"},
    "ホワイト": {"en": "White", "ru": "Белый"},
    "ブラック": {"en": "Black", "ru": "Черный"},
    "シルバー": {"en": "Silver", "ru": "Серебристый"},
    "グレー": {"en": "Gray", "ru": "Серый"},
    "レッド": {"en": "Red", "ru": "Красный"},
    "ブルー": {"en": "Blue", "ru": "Синий"},
    "グリーン": {"en": "Green", "ru": "Зеленый"},
    "パール": {"en": "Pearl", "ru": "Жемчужный"},
    "ミニバン": {"en": "Minivan", "ru": "Минивэн"},
    "SUV・クロカン": {"en": "SUV", "ru": "SUV"},
    "軽自動車": {"en": "Kei car", "ru": "Кей-кар"},
    "ハッチバック": {"en": "Hatchback", "ru": "Хэтчбек"},
    "セダン": {"en": "Sedan", "ru": "Седан"},
    "クーペ": {"en": "Coupe", "ru": "Купе"},
    "オープン": {"en": "Convertible", "ru": "Кабриолет"},
    "トラック": {"en": "Truck", "ru": "Грузовик"},
    "バン": {"en": "Van", "ru": "Фургон"},
    "愛知県": {"en": "Aichi", "ru": "Айти"},
    "東京都": {"en": "Tokyo", "ru": "Токио"},
    "大阪府": {"en": "Osaka", "ru": "Осака"},
}


def translate_text(text: str | None, lang: str) -> str | None:
    if text is None or lang == "ja":
        return text

    stripped = text.strip()
    if not stripped:
        return text
    if URL_RE.match(stripped):
        return stripped

    static = STATIC_TRANSLATIONS.get(stripped)
    if static and lang in static:
        return static[lang]

    return _translate_dynamic(stripped, lang)


@lru_cache(maxsize=4096)
def _translate_dynamic(text: str, lang: str) -> str:
    if GoogleTranslator is None:
        return text
    try:
        translated = GoogleTranslator(source="ja", target=lang).translate(text)
        return translated or text
    except Exception:
        return text


def slugify_text(text: str | None) -> str | None:
    if not text:
        return None

    base = translate_text(text, "en") or text
    slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
    return slug or None


def localize_listing_payload(payload: dict[str, Any], lang: str) -> dict[str, Any]:
    if lang == "ja":
        return payload

    localized: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, str):
            localized[key] = translate_text(value, lang)
        elif isinstance(value, list):
            localized[key] = [
                translate_text(item, lang) if isinstance(item, str) else item
                for item in value
            ]
        elif isinstance(value, dict):
            localized[key] = {
                nested_key: translate_text(nested_value, lang)
                if isinstance(nested_value, str)
                else nested_value
                for nested_key, nested_value in value.items()
            }
        else:
            localized[key] = value
    return localized
