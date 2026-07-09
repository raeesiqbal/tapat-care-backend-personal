import re
from typing import TypedDict

import zipcodes


US_ZIP_CODE_PATTERN = re.compile(r"^\d{5}(?:-\d{4})?$")


class ZipCodeDetails(TypedDict):
    zip_code: str
    city: str
    state: str
    formatted: str


def normalize_us_zip_code(value: str) -> str:
    zip_code = str(value or "").strip()

    if not US_ZIP_CODE_PATTERN.fullmatch(zip_code):
        raise ValueError("Enter a valid US ZIP code.")

    return zip_code[:5]


def get_us_zip_details(value: str) -> ZipCodeDetails:
    zip_code = normalize_us_zip_code(value)
    matches = zipcodes.matching(zip_code)

    if not matches:
        raise LookupError("ZIP code not found.")

    match = matches[0]
    city = str(match.get("city") or "").strip()
    state = str(match.get("state") or "").strip()

    if not city or not state:
        raise LookupError("ZIP code not found.")

    return {
        "zip_code": zip_code,
        "city": city,
        "state": state,
        "formatted": f"{city}, {state}",
    }
