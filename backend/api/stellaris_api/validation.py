"""Small strict request-validation helpers producing contract field_errors (JSON Pointer paths)."""

import math
import re
from datetime import datetime

from .errors import ApiError, validation_error

MAX_TEXT = 100_000
MAX_ITEMS = 200
_RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$")


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_finite(value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def is_timestamp(value) -> bool:
    if not isinstance(value, str) or not _RFC3339.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


class Validator:
    def __init__(self):
        self.errors = []

    def error(self, path: str, message: str) -> None:
        self.errors.append({"path": path, "message": message})

    def unknown(self, obj: dict, allowed, path: str = "") -> None:
        for key in sorted(obj):
            if key not in allowed:
                self.error(f"{path}/{key}", "Unknown field.")

    def object(self, value, path: str) -> bool:
        if not isinstance(value, dict):
            self.error(path, "Expected a JSON object.")
            return False
        return True

    def string(self, obj, key, path="", *, required=True, nullable=False, min_len=0,
               max_len=MAX_TEXT, strip=False, default=None):
        p = f"{path}/{key}"
        if key not in obj:
            if required:
                self.error(p, f"{key} is required.")
            return default
        value = obj[key]
        if value is None:
            if not nullable:
                self.error(p, f"{key} must be a string.")
            return None
        if not isinstance(value, str):
            self.error(p, f"{key} must be a string{' or null' if nullable else ''}.")
            return None
        if strip:
            value = value.strip()
        if not min_len <= len(value) <= max_len:
            self.error(p, f"{key} must contain {min_len}-{max_len} characters.")
        return value

    def enum(self, obj, key, choices, path="", *, required=True, default=None):
        p = f"{path}/{key}"
        if key not in obj:
            if required:
                self.error(p, f"{key} is required.")
            return default
        if obj[key] not in choices:
            self.error(p, f"{key} must be one of: {', '.join(choices)}.")
        return obj[key]

    def strings(self, obj, key, path="", *, required=True, max_items=MAX_ITEMS,
                max_len=MAX_TEXT, min_len=0, unique=False):
        p = f"{path}/{key}"
        if key not in obj:
            if required:
                self.error(p, f"{key} is required.")
            return []
        value = obj[key]
        if not isinstance(value, list) or len(value) > max_items:
            self.error(p, f"{key} must be an array of at most {max_items} strings.")
            return []
        for i, item in enumerate(value):
            if not isinstance(item, str) or not min_len <= len(item) <= max_len:
                self.error(f"{p}/{i}", f"Expected a string of {min_len}-{max_len} characters.")
        if unique and len(set(map(str, value))) != len(value):
            self.error(p, f"{key} must not contain duplicates.")
        return value

    def check(self) -> None:
        if self.errors:
            raise validation_error(self.errors)


def invalid_reference(errors) -> ApiError:
    return ApiError(422, "INVALID_REFERENCE", "A referenced resource does not exist in this project or is not ready.",
                    details={"field_errors": errors})
