"""MongoDB store for foodlog (peer DB to Cabinet on the same server)."""

from __future__ import annotations

import datetime
import json
import os
from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

FOODLOG_DB_NAME = "foodlog"
DAYS_COLLECTION = "days"
LOOKUP_COLLECTION = "lookup"


def _noon_utc(day: str) -> datetime.datetime:
    d = datetime.date.fromisoformat(day)
    return datetime.datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=datetime.timezone.utc)


def normalize_calories(calories: Any) -> int:
    """Coerce calorie values (int, numeric str, or nested dict) to int."""
    if isinstance(calories, dict):
        return int(calories.get("calories", 0) or 0)
    if isinstance(calories, str) and calories.isnumeric():
        return int(calories)
    return int(calories)


def day_total_calories(entries: list) -> int:
    """Sum calorie counts for a list of food log entries."""
    return sum(normalize_calories(e.get("calories", 0)) for e in entries)


def is_submitted_value(value: Any) -> bool:
    """Interpret submitted flag from bool or ``{\"submitted\": bool}`` shapes."""
    if isinstance(value, dict):
        return bool(value.get("submitted"))
    return bool(value)


class FoodlogStore:
    """
    Source of truth for foodlog on the same MongoDB server as Cabinet.

    Database: ``foodlog`` (peer to Cabinet's ``cabinet`` DB).
    Collections: ``days`` (one doc per ISO date), ``lookup`` (food calorie/type).
    """

    def __init__(
        self,
        connection_string: str | None = None,
        db_name: str = FOODLOG_DB_NAME,
        client: MongoClient | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            uri = (connection_string or os.environ.get("FOODLOG_MONGO_URI") or "").strip()
            if not uri:
                # Same server as Cabinet; Cabinet config is the usual source.
                try:
                    from cabinet import Cabinet

                    cab = Cabinet()
                    uri = (getattr(cab, "mongodb_connection_string", None) or "").strip()
                except Exception:  # pylint: disable=broad-exception-caught
                    uri = ""
            if not uri:
                uri = "mongodb://localhost:27017/"
            self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self._owns_client = True
        self.db: Database = self._client[db_name]
        self.days: Collection = self.db[DAYS_COLLECTION]
        self.lookup: Collection = self.db[LOOKUP_COLLECTION]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        self.days.create_index([("date", ASCENDING)], unique=True)
        self.days.create_index([("date_time", ASCENDING)])
        self.lookup.create_index([("food", ASCENDING)], unique=True)

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def ping(self) -> bool:
        self._client.admin.command("ping")
        return True

    def get_day(self, day: str) -> dict | None:
        return self.days.find_one({"_id": day})

    def get_entries(self, day: str) -> list[dict]:
        doc = self.get_day(day)
        if not doc:
            return []
        return list(doc.get("entries") or [])

    def list_days_between(self, start: str, end: str) -> dict[str, list]:
        """Return ``{iso_date: entries}`` for dates in ``[start, end]`` inclusive."""
        cursor = self.days.find(
            {"_id": {"$gte": start, "$lte": end}},
            projection={"entries": 1},
        )
        return {doc["_id"]: list(doc.get("entries") or []) for doc in cursor}

    def all_days_map(self) -> dict[str, list]:
        """Legacy food.json-shaped map of all days → entries."""
        out: dict[str, list] = {}
        for doc in self.days.find({}, projection={"entries": 1}):
            out[doc["_id"]] = list(doc.get("entries") or [])
        return out

    def is_day_submitted(self, day: str) -> bool:
        doc = self.get_day(day)
        if not doc:
            return False
        return bool(doc.get("submitted"))

    def _write_day(
        self,
        day: str,
        entries: list[dict],
        *,
        submitted: bool | None = None,
        submitted_at: str | None = None,
    ) -> dict:
        existing = self.get_day(day)
        if submitted is None:
            submitted = bool(existing.get("submitted")) if existing else False
        if submitted_at is None and existing:
            submitted_at = existing.get("submitted_at")
        now = datetime.datetime.now(datetime.timezone.utc)
        normalized = [
            {
                "food": str(e.get("food", "unknown")).lower(),
                "calories": normalize_calories(e.get("calories", 0)),
            }
            for e in entries
        ]
        doc = {
            "_id": day,
            "date": day,
            "date_time": _noon_utc(day),
            "entries": normalized,
            "total_calories": day_total_calories(normalized),
            "entry_count": len(normalized),
            "submitted": submitted,
            "submitted_at": submitted_at,
            "updated_at": now,
        }
        self.days.replace_one({"_id": day}, doc, upsert=True)
        return doc

    def append_entry(self, day: str, food: str, calories: int) -> dict:
        entries = self.get_entries(day)
        entries.append({"food": food.lower(), "calories": normalize_calories(calories)})
        return self._write_day(day, entries)

    def pop_latest_entry(self, day: str) -> dict | None:
        entries = self.get_entries(day)
        if not entries:
            return None
        removed = entries.pop()
        if entries:
            self._write_day(day, entries)
        else:
            self.days.delete_one({"_id": day})
        return removed

    def mark_submitted(self, day: str | None = None) -> str:
        day = day or datetime.date.today().isoformat()
        entries = self.get_entries(day)
        submitted_at = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        self._write_day(day, entries, submitted=True, submitted_at=submitted_at)
        return day

    def get_lookup(self) -> dict[str, dict]:
        """food.json-lookup shaped dict keyed by lowercase food name."""
        out: dict[str, dict] = {}
        for doc in self.lookup.find():
            food = doc.get("food") or doc.get("_id")
            out[str(food).lower()] = {
                "calories": normalize_calories(doc.get("calories", 0)),
                "type": doc.get("type", "unknown"),
            }
        return out

    def upsert_lookup(
        self, food: str, calories: int, food_type: str | None = None
    ) -> None:
        food_l = food.lower()
        existing = self.lookup.find_one({"_id": food_l})
        doc = {
            "_id": food_l,
            "food": food_l,
            "calories": normalize_calories(calories),
            "type": food_type
            or (existing.get("type") if existing else None)
            or "unknown",
        }
        self.lookup.replace_one({"_id": food_l}, doc, upsert=True)

    def set_lookup_type(self, food: str, food_type: str) -> None:
        food_l = food.lower()
        existing = self.lookup.find_one({"_id": food_l}) or {
            "_id": food_l,
            "food": food_l,
            "calories": 0,
        }
        existing["type"] = food_type
        existing["food"] = food_l
        self.lookup.replace_one({"_id": food_l}, existing, upsert=True)

    def replace_all_from_maps(
        self,
        log_data: dict,
        lookup_data: dict | None = None,
        submitted_data: dict | None = None,
    ) -> int:
        """Import food.json / food_lookup.json / food_submitted.json shaped maps."""
        submitted_data = submitted_data or {}
        count = 0
        for day, entries in log_data.items():
            if not isinstance(entries, list):
                continue
            sub = submitted_data.get(day)
            submitted = is_submitted_value(sub)
            submitted_at = None
            if isinstance(sub, dict):
                submitted_at = sub.get("submitted_at")
            self._write_day(
                day,
                entries,
                submitted=submitted,
                submitted_at=submitted_at,
            )
            count += 1
        if lookup_data:
            for food, meta in lookup_data.items():
                if not isinstance(meta, dict):
                    continue
                self.upsert_lookup(
                    food,
                    meta.get("calories", 0),
                    food_type=meta.get("type", "unknown"),
                )
        # Submitted-only days with no entries
        for day, sub in submitted_data.items():
            if self.get_day(day):
                continue
            if is_submitted_value(sub):
                submitted_at = sub.get("submitted_at") if isinstance(sub, dict) else None
                self._write_day(day, [], submitted=True, submitted_at=submitted_at)
                count += 1
        return count

    def migrate_from_json_files(
        self,
        food_log_file: str,
        food_lookup_file: str,
        food_submitted_file: str,
        *,
        only_if_empty: bool = True,
    ) -> int:
        """Import flat files into Mongo. Returns days imported (0 if skipped)."""
        if only_if_empty and self.days.estimated_document_count() > 0:
            return 0

        def _load(path: str) -> dict:
            if not os.path.exists(path):
                return {}
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        return self.replace_all_from_maps(
            _load(food_log_file),
            _load(food_lookup_file),
            _load(food_submitted_file),
        )

    def export_log_map(self) -> dict:
        return self.all_days_map()

    def export_lookup_map(self) -> dict:
        return self.get_lookup()

    def export_submitted_map(self) -> dict:
        out: dict = {}
        for doc in self.days.find({"submitted": True}):
            out[doc["_id"]] = {
                "submitted": True,
                "submitted_at": doc.get("submitted_at"),
            }
        return out


_STORE: FoodlogStore | None = None


def get_store() -> FoodlogStore:
    """Process-wide FoodlogStore (lazy)."""
    global _STORE  # pylint: disable=global-statement
    if _STORE is None:
        _STORE = FoodlogStore()
    return _STORE


def reset_store_for_tests(store: FoodlogStore | None = None) -> None:
    """Test helper to inject/clear the singleton."""
    global _STORE  # pylint: disable=global-statement
    _STORE = store
