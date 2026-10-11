"""Pure build and plan of the library section of the Home Keeper export.

Home Keeper does 1 export and 1 import for itself and for each companion that
registers the ``import_export`` capability (``docs/INTEGRATING.md`` of Home
Keeper, section 11). The library section is the ``data`` that
:func:`build_export` makes. It has 1 list for each section of the document.

* :func:`build_export` makes the ``data`` from the document. The caller gives
  the names of the people, the areas and the to-do entities, so the data is
  portable, and the relative path of each cover file that it copied.
* :func:`plan_import` plans an import of that ``data`` on a copy of the
  document. It changes no argument, so a dry run is the same call with the
  result thrown away. The import is an upsert: it matches a record by its id,
  then by a natural key, and it never deletes a record.
* :func:`check_files_dir` refuses a ``files_dir`` that is not below
  ``<config>/.storage/home_keeper_import_export/``.

A value that only 1 install knows is not exported (:data:`EXCLUDED_KEYS`). The
syncs make it again after the import.

This module imports no Home Assistant code.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from .csv_io import _Index as BookIndex
from .models import (
    BOOK_FIELDS,
    COPY_FIELDS,
    COVER_KINDS,
    MAX_NAME,
    MAX_NOTE,
    READING_FIELDS,
    LibraryError,
    apply_person_settings,
    book_field,
    boolean,
    build_book,
    build_bookcase,
    build_copy,
    build_loan,
    build_room,
    build_shelf,
    clone,
    copy_field,
    empty_reading,
    fold,
    integer,
    iso_date,
    new_id,
    next_order,
    person_settings,
    reading_field,
    text,
    title_key,
    update_location,
)

#: The format of the ``data``. It goes up only when the meaning of a key changes.
FORMAT = 1

#: The sections of the ``data``, in the order of the import.
SECTIONS = (
    "rooms",
    "bookcases",
    "shelves",
    "books",
    "copies",
    "loans",
    "reading",
    "people",
)

#: ``{section: ((key, reason), ...)}``: each stored key that the export drops.
#: ``wishlist`` is the wishlist entry of a book, and ``document`` is the top
#: level of the stored document.
EXCLUDED_KEYS: dict[str, tuple[tuple[str, str], ...]] = {
    "document": (
        (
            "todo_orphans",
            "to-do items of this install that the wishlist sync removes",
        ),
    ),
    "books": (
        (
            "lookup_tries",
            "bookkeeping of the lookup queue of this install; a book starts at 0",
        ),
    ),
    "loans": (
        (
            "hk_task_id",
            "a Home Keeper task id that only this install knows; the loan sync "
            "makes the task again",
        ),
    ),
    "wishlist": (
        (
            "todo_uid",
            "a to-do item uid that only this install knows; the wishlist sync "
            "makes the item again",
        ),
        (
            "todo_entity",
            "the to-do list of that item; the wishlist sync finds it from the "
            "wishlist_todo of the person",
        ),
    ),
}

#: The keys that the export adds next to an id: the name of the record.
NAME_KEYS = ("area_name", "person_name", "wishlist_todo_name")

#: The root of ``files_dir``, below the config directory.
FILES_ROOT = (".storage", "home_keeper_import_export")
#: The directory of the cover files in ``files_dir``.
COVERS_SUBDIR = "covers"

LEVEL_ERROR = "error"
LEVEL_WARNING = "warning"

ACTION_CREATE = "create"
ACTION_UPDATE = "update"

_RECORD_ID_RE = re.compile(r"[0-9a-f]{32}")
_COVER_FILE_RE = re.compile(r"covers/[A-Za-z0-9_-]{1,100}\.(?:jpg|jpeg|png|webp)")


def _excluded(section: str) -> set[str]:
    return {key for key, _reason in EXCLUDED_KEYS.get(section, ())}


# ── files_dir ────────────────────────────────────────────────────────────────


def check_files_dir(files_dir: Any, config_dir: str) -> str:
    """The normalized absolute path of *files_dir*, or ``files_dir_invalid``.

    The path must be at or below ``<config_dir>/.storage/home_keeper_import_export``.
    A relative path is read from *config_dir*, and a relative path with ``..`` is
    refused. This function reads no file: the caller resolves symbolic links
    and calls it again.
    """
    if not isinstance(files_dir, str) or not files_dir.strip() or "\0" in files_dir:
        raise LibraryError("files_dir_invalid")
    raw = files_dir.strip()
    if not os.path.isabs(raw):
        if ".." in PurePath(raw).parts:
            raise LibraryError("files_dir_invalid")
        raw = os.path.join(config_dir, raw)
    base = os.path.normpath(os.path.join(config_dir, *FILES_ROOT))
    path = os.path.normpath(raw)
    if os.path.commonpath([base, path]) != base:
        raise LibraryError("files_dir_invalid")
    return path


def cover_export_path(book_id: str) -> str:
    """The relative path of the cover file of a book in ``files_dir``."""
    return f"{COVERS_SUBDIR}/{book_id}.jpg"


def is_cover_path(value: Any) -> bool:
    """Whether *value* is a relative cover path that the import reads."""
    return isinstance(value, str) and _COVER_FILE_RE.fullmatch(value) is not None


# ── Export ───────────────────────────────────────────────────────────────────


def covers_to_copy(state: dict[str, Any]) -> list[tuple[str, str]]:
    """``(book_id, stored file)`` for each book with a cover file, by book id."""
    out = []
    for book_id in sorted(state["books"]):
        cover = state["books"][book_id].get("cover") or {}
        file = cover.get("file")
        if cover.get("kind", "none") != "none" and isinstance(file, str) and file:
            out.append((book_id, file))
    return out


def _ordered(records: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        records.values(),
        key=lambda r: (int(r.get("order", 0)), fold(r.get("name")), r["id"]),
    )


def _without(record: dict[str, Any], section: str) -> dict[str, Any]:
    drop = _excluded(section)
    return {key: clone(value) for key, value in record.items() if key not in drop}


def build_export(
    state: dict[str, Any],
    *,
    person_names: dict[str, str],
    area_names: dict[str, str],
    entity_names: dict[str, str],
    cover_files: dict[str, str],
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return ``(data, skipped)`` for the library section of the export.

    *cover_files* maps a book id to the relative path of the cover file that
    the caller copied. A book with a cover file that is not in *cover_files*
    gets ``cover: None`` and is counted in ``skipped["covers"]``.
    """
    skipped = {"covers": 0}
    data: dict[str, Any] = {"format": FORMAT}
    rooms = []
    for room in _ordered(state["rooms"]):
        record = _without(room, "rooms")
        area_id = room.get("area_id")
        record["area_name"] = area_names.get(area_id) if area_id else None
        rooms.append(record)
    data["rooms"] = rooms
    data["bookcases"] = [_without(b, "bookcases") for b in _ordered(state["bookcases"])]
    data["shelves"] = [_without(s, "shelves") for s in _ordered(state["shelves"])]
    books = []
    for book_id in sorted(state["books"]):
        book = state["books"][book_id]
        record = _without(book, "books")
        cover = book.get("cover") or {}
        if book_id in cover_files:
            record["cover"] = {"kind": cover.get("kind"), "file": cover_files[book_id]}
        else:
            if cover.get("file"):
                skipped["covers"] += 1
            record["cover"] = None
        wish = book.get("wishlist")
        if isinstance(wish, dict):
            entry = _without(wish, "wishlist")
            entry["person_name"] = person_names.get(str(wish.get("person_id")))
            record["wishlist"] = entry
        books.append(record)
    data["books"] = books
    data["copies"] = [
        _without(state["copies"][key], "copies") for key in sorted(state["copies"])
    ]
    loans = []
    for key in sorted(state["loans"]):
        loan = state["loans"][key]
        record = _without(loan, "loans")
        person_id = loan.get("person_id")
        record["person_name"] = person_names.get(person_id) if person_id else None
        loans.append(record)
    data["loans"] = loans
    data["reading"] = [
        {
            "person_id": person_id,
            "person_name": person_names.get(person_id),
            "books": [
                {"book_id": book_id, **clone(rows[book_id])} for book_id in sorted(rows)
            ],
        }
        for person_id, rows in sorted(state["reading"].items())
        if rows
    ]
    people = []
    for person_id in sorted(state["people"]):
        settings = person_settings(state["people"], person_id)
        todo = settings.get("wishlist_todo")
        people.append(
            {
                "person_id": person_id,
                "person_name": person_names.get(person_id),
                **settings,
                "wishlist_todo_name": entity_names.get(todo) if todo else None,
            }
        )
    data["people"] = people
    return data, skipped


# ── Import ───────────────────────────────────────────────────────────────────


@dataclass
class Problem:
    """1 problem of an import: ``key`` and ``placeholders`` make the message."""

    level: str
    path: str
    key: str
    placeholders: dict[str, str] = field(default_factory=dict)


@dataclass
class CoverJob:
    """A cover file that the caller reads from ``files_dir`` after the write."""

    book_id: str
    kind: str
    file: str
    path: str


@dataclass
class ImportPlan:
    """The planned document and the report of an import."""

    state: dict[str, Any]
    problems: list[Problem] = field(default_factory=list)
    records: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    covers: list[CoverJob] = field(default_factory=list)
    lookup_ids: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the import can be written: no problem of level ``error``."""
        return not any(p.level == LEVEL_ERROR for p in self.problems)


class _Refs:
    """Finds a person, an area or a to-do entity of this install by id, then name."""

    def __init__(self, names: dict[str, str]) -> None:
        self._names = names
        self._by_name: dict[str, str | None] = {}
        for key, name in names.items():
            folded = fold(name)
            if folded:
                # 2 records with 1 name match neither.
                self._by_name[folded] = None if folded in self._by_name else key

    def find(self, ref_id: Any, name: Any) -> str | None:
        if isinstance(ref_id, str) and ref_id in self._names:
            return ref_id
        return self._by_name.get(fold(name)) if fold(name) else None


class _Planner:
    def __init__(
        self,
        state: dict[str, Any],
        document: Any,
        *,
        persons: dict[str, str],
        areas: dict[str, str],
        todo_entities: dict[str, str],
        now: str,
    ) -> None:
        self.new = clone(state)
        self.plan = ImportPlan(state=self.new)
        self.document = document
        self.persons = _Refs(persons)
        self.areas = _Refs(areas)
        self.todos = _Refs(todo_entities)
        self.now = now
        self.today = now[:10]
        self.maps: dict[str, dict[str, str]] = {name: {} for name in SECTIONS}
        self.person_map: dict[str, str | None] = {}
        for name in SECTIONS:
            self.plan.counts[name] = {"created": 0, "updated": 0, "skipped": 0}

    # ── Report helpers ───────────────────────────────────────────────────────

    def problem(self, level: str, path: str, key: str, **placeholders: Any) -> None:
        self.plan.problems.append(
            Problem(level, path, key, {k: str(v) for k, v in placeholders.items()})
        )

    def error(self, path: str, err: LibraryError) -> None:
        self.plan.problems.append(Problem(LEVEL_ERROR, path, err.key, err.placeholders))

    def record(
        self,
        section: str,
        index: int,
        record_id: str,
        name: str,
        action: str,
        matched_by: str | None,
    ) -> None:
        self.plan.records.append(
            {
                "section": section,
                "index": index,
                "id": record_id,
                "name": name,
                "action": action,
                "matched_by": matched_by,
            }
        )
        self.plan.counts[section][
            "created" if action == ACTION_CREATE else "updated"
        ] += 1

    def skip(self, section: str) -> None:
        self.plan.counts[section]["skipped"] += 1

    # ── Shared steps ─────────────────────────────────────────────────────────

    def items(self, section: str) -> list[tuple[int, str, dict[str, Any]]]:
        """``(index, path, record)`` for each record of a section of the document."""
        value = self.document.get(section)
        if value is None:
            return []
        if not isinstance(value, list):
            self.problem(LEVEL_ERROR, section, "import_not_a_list", field=section)
            return []
        out = []
        for index, record in enumerate(value):
            path = f"{section}[{index}]"
            if isinstance(record, dict):
                out.append((index, path, record))
            else:
                self.problem(LEVEL_ERROR, path, "import_not_an_object", field=path)
        return out

    def target_id(self, section: str, raw: Any) -> str:
        """The id of a new record: the id of the document if it is free."""
        if (
            isinstance(raw, str)
            and _RECORD_ID_RE.fullmatch(raw)
            and raw not in self.new[section]
        ):
            return raw
        return new_id()

    def ref(self, section: str, raw: Any) -> str | None:
        """The record of this install for an id of the document, or None."""
        if not isinstance(raw, str) or not raw:
            return None
        if raw in self.maps[section]:
            return self.maps[section][raw]
        return raw if raw in self.new[section] else None

    def required_ref(
        self, section: str, record: dict[str, Any], key: str, path: str
    ) -> str | None:
        found = self.ref(section, record.get(key))
        if found is None:
            self.problem(
                LEVEL_ERROR,
                f"{path}.{key}",
                "import_reference_missing",
                field=key,
                id=record.get(key),
            )
        return found

    def person(self, record: dict[str, Any], path: str) -> str | None:
        """The person of this install for the ``person_id`` of a record."""
        raw = record.get("person_id")
        name = record.get("person_name")
        key = f"{raw}|{name}"
        if key not in self.person_map:
            self.person_map[key] = self.persons.find(raw, name)
        found = self.person_map[key]
        if found is None:
            self.problem(
                LEVEL_WARNING,
                f"{path}.person_id",
                "import_person_not_found",
                name=name or raw or "",
            )
        return found

    def check(self, path: str, func: Any, *args: Any) -> tuple[bool, Any]:
        """``(True, value)``, or ``(False, None)`` with an error problem."""
        try:
            return True, func(*args)
        except LibraryError as err:
            self.error(path, err)
            return False, None

    # ── Locations ────────────────────────────────────────────────────────────

    def locations(self, section: str, kind: str, parent: str | None) -> None:
        parent_section = {"bookcases": "rooms", "shelves": "bookcases"}.get(section)
        for index, path, record in self.items(section):
            data: dict[str, Any] = {}
            ok, data["name"] = self.check(
                f"{path}.name",
                lambda v: text(v, "name", MAX_NAME, required=True),
                record.get("name"),
            )
            if record.get("order") is not None:
                good, data["order"] = self.check(
                    f"{path}.order",
                    lambda v: integer(v, "order", low=0, high=1_000_000),
                    record["order"],
                )
                ok = ok and good
            if section == "bookcases":
                good, data["note"] = self.check(
                    f"{path}.note",
                    lambda v: text(v, "note", MAX_NOTE),
                    record.get("note"),
                )
                ok = ok and good
            if section == "rooms":
                self.area(record, path, data)
            if parent and parent_section:
                found = self.required_ref(parent_section, record, parent, path)
                ok = ok and found is not None
                data[parent] = found
            if ok:
                self.upsert_location(section, kind, parent, index, record, data)

    def area(self, record: dict[str, Any], path: str, data: dict[str, Any]) -> None:
        """Set ``area_id`` in *data*. An area that this install lacks is left out."""
        raw = record.get("area_id")
        name = record.get("area_name")
        if not raw and not name:
            data["area_id"] = None
            return
        found = self.areas.find(raw, name)
        if found is None:
            self.problem(
                LEVEL_WARNING,
                f"{path}.area_id",
                "import_area_not_found",
                name=name or raw or "",
            )
            return
        data["area_id"] = found

    def upsert_location(
        self,
        section: str,
        kind: str,
        parent: str | None,
        index: int,
        record: dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        records = self.new[section]
        matched_by = None
        target = None
        raw = record.get("id")
        if isinstance(raw, str) and raw in records:
            target, matched_by = raw, "id"
        else:
            wanted = fold(data["name"])
            for key in sorted(records):
                other = records[key]
                if fold(other.get("name")) == wanted and (
                    parent is None or other.get(parent) == data[parent]
                ):
                    target, matched_by = key, "name"
                    break
        if target is None:
            builders = {"rooms": build_room, "bookcases": build_bookcase}
            builder = builders.get(section, build_shelf)
            siblings = {parent: data[parent]} if parent else {}
            created = builder(data, order=next_order(records, **siblings))
            created["id"] = self.target_id(section, raw)
            records[created["id"]] = created
            target = created["id"]
            action = ACTION_CREATE
        else:
            records[target], _changed = update_location(kind, records[target], data)
            action = ACTION_UPDATE
        if isinstance(raw, str) and raw:
            self.maps[section][raw] = target
        self.record(section, index, target, data["name"], action, matched_by)

    # ── Books ────────────────────────────────────────────────────────────────

    def books(self) -> None:
        index = BookIndex(self.new["books"])
        for position, path, record in self.items("books"):
            fields: dict[str, Any] = {}
            ok = True
            for name in BOOK_FIELDS:
                if name not in record:
                    continue
                good, fields[name] = self.check(
                    f"{path}.{name}", book_field, name, record[name]
                )
                ok = ok and good
            if not fields.get("title") and ok:
                self.problem(
                    LEVEL_ERROR, f"{path}.title", "field_required", field="title"
                )
                ok = False
            cover = self.cover(record.get("cover"), f"{path}.cover")
            wish = record.get("wishlist")
            if wish is not None and not isinstance(wish, dict):
                self.problem(
                    LEVEL_ERROR,
                    f"{path}.wishlist",
                    "import_not_an_object",
                    field=f"{path}.wishlist",
                )
                ok = False
            if not ok:
                continue
            raw = record.get("id")
            key = {
                "book_id": raw,
                "isbn13": fields.get("isbn13"),
                "isbn10": fields.get("isbn10"),
                "title": fields["title"],
                "authors": fields.get("authors") or [],
            }
            target, matched_by = _match_book(index, key)
            if target is None:
                book = self.new_book(raw, fields, record)
                index.add(book)
                target = book["id"]
                action = ACTION_CREATE
                if book["needs_details"]:
                    self.plan.lookup_ids.append(target)
            else:
                book = self.new["books"][target]
                changed = False
                for name, value in fields.items():
                    if book.get(name) != value:
                        book[name] = value
                        changed = True
                if changed:
                    book["updated_at"] = self.now
                action = ACTION_UPDATE
            if isinstance(raw, str) and raw:
                self.maps["books"][raw] = target
            if cover is not None:
                self.plan.covers.append(
                    CoverJob(target, cover[0], cover[1], f"{path}.cover.file")
                )
            if isinstance(wish, dict):
                self.wishlist(target, wish, f"{path}.wishlist")
            self.record("books", position, target, fields["title"], action, matched_by)

    def new_book(
        self, raw: Any, fields: dict[str, Any], record: dict[str, Any]
    ) -> dict[str, Any]:
        book = build_book(fields, now=self.now)
        book["id"] = self.target_id("books", raw)
        for stamp in ("created_at", "updated_at"):
            if isinstance(record.get(stamp), str) and record[stamp]:
                book[stamp] = record[stamp]
        self.new["books"][book["id"]] = book
        return book

    def cover(self, value: Any, path: str) -> tuple[str, str] | None:
        """``(kind, file)`` of a cover with a file, else None."""
        if not isinstance(value, dict):
            return None
        kind = value.get("kind")
        file = value.get("file")
        if kind not in COVER_KINDS or kind == "none" or file is None:
            return None
        if not is_cover_path(file):
            self.problem(
                LEVEL_WARNING, f"{path}.file", "import_cover_unreadable", file=file
            )
            return None
        return str(kind), str(file)

    def wishlist(self, book_id: str, wish: dict[str, Any], path: str) -> None:
        person_id = self.person(wish, path)
        if person_id is None:
            return
        ok, buy = self.check(f"{path}.buy", boolean, wish.get("buy", False), "buy")
        good, bought = self.check(
            f"{path}.bought", boolean, wish.get("bought", False), "bought"
        )
        if not (ok and good):
            return
        book = self.new["books"][book_id]
        entry = dict(book.get("wishlist") or {})
        added = wish.get("added_at")
        entry.update(
            {
                "person_id": person_id,
                "buy": buy,
                "bought": bought,
                "added_at": added if isinstance(added, str) and added else self.now,
            }
        )
        entry.setdefault("todo_uid", None)
        entry.setdefault("todo_entity", None)
        if entry != book.get("wishlist"):
            book["wishlist"] = entry

    # ── Copies ───────────────────────────────────────────────────────────────

    def copies(self) -> None:
        for index, path, record in self.items("copies"):
            book_id = self.required_ref("books", record, "book_id", path)
            data: dict[str, Any] = {}
            ok = book_id is not None
            for name in COPY_FIELDS:
                if name == "shelf_id" or name not in record:
                    continue
                good, data[name] = self.check(
                    f"{path}.{name}", copy_field, name, record[name]
                )
                ok = ok and good
            if not ok:
                continue
            raw_shelf = record.get("shelf_id")
            shelf_id = self.ref("shelves", raw_shelf)
            if raw_shelf and shelf_id is None:
                self.problem(
                    LEVEL_WARNING,
                    f"{path}.shelf_id",
                    "import_reference_missing",
                    field="shelf_id",
                    id=raw_shelf,
                )
            data["shelf_id"] = shelf_id
            data["book_id"] = book_id
            raw = record.get("id")
            title = str(self.new["books"][str(book_id)].get("title", ""))
            if isinstance(raw, str) and raw in self.new["copies"]:
                copy = self.new["copies"][raw]
                copy.update(data)
                self.maps["copies"][raw] = raw
                self.record("copies", index, raw, title, ACTION_UPDATE, "id")
                continue
            copy = build_copy(data, now=self.now)
            copy["id"] = self.target_id("copies", raw)
            if isinstance(record.get("created_at"), str) and record["created_at"]:
                copy["created_at"] = record["created_at"]
            self.new["copies"][copy["id"]] = copy
            if isinstance(raw, str) and raw:
                self.maps["copies"][raw] = copy["id"]
            self.record("copies", index, copy["id"], title, ACTION_CREATE, None)

    # ── Loans ────────────────────────────────────────────────────────────────

    def loans(self) -> None:
        for index, path, record in self.items("loans"):
            book_id = self.required_ref("books", record, "book_id", path)
            ok = book_id is not None
            copy_id = None
            if record.get("direction") == "out":
                copy_id = self.required_ref("copies", record, "copy_id", path)
                ok = ok and copy_id is not None
            person_id = None
            if record.get("person_id") or record.get("person_name"):
                person_id = self.person(record, path)
                if person_id is None and record.get("direction") == "in":
                    self.skip("loans")
                    continue
            if not ok:
                continue
            data = {
                key: record.get(key)
                for key in ("direction", "party", "format", "started", "due", "note")
            }
            data.update(
                {"book_id": book_id, "copy_id": copy_id, "person_id": person_id}
            )
            good, loan = self.check(path, _loan, data, record, self.today)
            if not good:
                continue
            raw = record.get("id")
            title = str(self.new["books"][str(book_id)].get("title", ""))
            if isinstance(raw, str) and raw in self.new["loans"]:
                current = self.new["loans"][raw]
                loan["id"] = raw
                loan["hk_task_id"] = current.get("hk_task_id")
                self.new["loans"][raw] = loan
                self.record("loans", index, raw, title, ACTION_UPDATE, "id")
                continue
            loan["id"] = self.target_id("loans", raw)
            self.new["loans"][loan["id"]] = loan
            self.record("loans", index, loan["id"], title, ACTION_CREATE, None)

    # ── Reading ──────────────────────────────────────────────────────────────

    def reading(self) -> None:
        for _index, path, entry in self.items("reading"):
            person_id = self.person(entry, path)
            rows = entry.get("books")
            if not isinstance(rows, list):
                self.problem(
                    LEVEL_ERROR, f"{path}.books", "import_not_a_list", field="books"
                )
                continue
            if person_id is None:
                self.plan.counts["reading"]["skipped"] += len(rows)
                continue
            for position, row in enumerate(rows):
                self.reading_row(person_id, position, row, f"{path}.books[{position}]")

    def reading_row(self, person_id: str, position: int, row: Any, path: str) -> None:
        if not isinstance(row, dict):
            self.problem(LEVEL_ERROR, path, "import_not_an_object", field=path)
            return
        book_id = self.required_ref("books", row, "book_id", path)
        values: dict[str, Any] = {}
        ok = book_id is not None
        for name in READING_FIELDS:
            if name in row:
                good, values[name] = self.check(
                    f"{path}.{name}", reading_field, name, row[name]
                )
                ok = ok and good
        if not ok or book_id is None:
            return
        rows = self.new["reading"].setdefault(person_id, {})
        current = rows.get(book_id)
        updated = dict(current) if current else empty_reading(now=self.now)
        updated.update(values)
        if current is None or any(
            updated.get(name) != current.get(name) for name in READING_FIELDS
        ):
            stamp = row.get("updated_at")
            updated["updated_at"] = (
                stamp if isinstance(stamp, str) and stamp else self.now
            )
        else:
            updated = current
        rows[book_id] = updated
        title = str(self.new["books"][book_id].get("title", ""))
        action = ACTION_UPDATE if current is not None else ACTION_CREATE
        self.record("reading", position, book_id, title, action, None)

    # ── People ───────────────────────────────────────────────────────────────

    def people(self) -> None:
        for index, path, record in self.items("people"):
            person_id = self.person(record, path)
            if person_id is None:
                self.skip("people")
                continue
            data: dict[str, Any] = {
                k: record[k] for k in ("share_reading", "yearly_goal") if k in record
            }
            todo = record.get("wishlist_todo")
            todo_name = record.get("wishlist_todo_name")
            if todo or todo_name:
                found = self.todos.find(todo, todo_name)
                if found is None:
                    self.problem(
                        LEVEL_WARNING,
                        f"{path}.wishlist_todo",
                        "import_todo_not_found",
                        name=todo_name or todo or "",
                    )
                else:
                    data["wishlist_todo"] = found
            elif "wishlist_todo" in record:
                data["wishlist_todo"] = None
            current = person_settings(self.new["people"], person_id)
            ok, result = self.check(path, apply_person_settings, current, data)
            if not ok:
                continue
            existed = person_id in self.new["people"]
            self.new["people"][person_id] = result[0]
            name = str(record.get("person_name") or person_id)
            action = ACTION_UPDATE if existed else ACTION_CREATE
            self.record("people", index, person_id, name, action, None)

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self) -> ImportPlan:
        if not isinstance(self.document, dict):
            self.problem(LEVEL_ERROR, "", "import_not_an_object", field="document")
            return self.plan
        fmt = self.document.get("format", FORMAT)
        if isinstance(fmt, bool) or not isinstance(fmt, int) or fmt < 1:
            self.problem(LEVEL_ERROR, "format", "invalid_field", field="format")
            return self.plan
        if fmt > FORMAT:
            self.problem(
                LEVEL_ERROR, "format", "import_format_too_new", format=fmt, max=FORMAT
            )
            return self.plan
        self.locations("rooms", "room", None)
        self.locations("bookcases", "bookcase", "room_id")
        self.locations("shelves", "shelf", "bookcase_id")
        self.books()
        self.copies()
        self.loans()
        self.reading()
        self.people()
        self.new["reading"] = {p: r for p, r in self.new["reading"].items() if r}
        return self.plan


def _match_book(index: BookIndex, key: dict[str, Any]) -> tuple[str | None, str | None]:
    """``(book_id, matched_by)``: by id, ISBN-13, ISBN-10, then title and author."""
    if key["book_id"] in index.by_id:
        return str(key["book_id"]), "id"
    if key["isbn13"] and key["isbn13"] in index.isbn13:
        return index.isbn13[key["isbn13"]], "isbn13"
    if key["isbn10"] and key["isbn10"] in index.isbn10:
        return index.isbn10[key["isbn10"]], "isbn10"
    found = index.title.get(title_key(key["title"], key["authors"]))
    return (found, "title") if found else (None, None)


def _loan(data: dict[str, Any], record: dict[str, Any], today: str) -> dict[str, Any]:
    """A checked loan record from the fields of the document."""
    loan = build_loan(data, today=today)
    loan["returned"] = iso_date(record.get("returned"), "returned")
    loan["add_task"] = boolean(record.get("add_task", True), "add_task")
    loan["overdue_fired"] = boolean(record.get("overdue_fired", False), "overdue_fired")
    return loan


def plan_import(
    state: dict[str, Any],
    document: Any,
    *,
    persons: dict[str, str],
    areas: dict[str, str],
    todo_entities: dict[str, str],
    now: str,
) -> ImportPlan:
    """Plan the import of *document* on a copy of *state*.

    *persons*, *areas* and *todo_entities* map each id of this install to its
    name. ``plan.state`` is the planned document. *state* does not change.
    """
    return _Planner(
        state,
        document,
        persons=persons,
        areas=areas,
        todo_entities=todo_entities,
        now=now,
    ).run()


def report(
    plan: ImportPlan, *, dry_run: bool, messages: dict[int, str]
) -> dict[str, Any]:
    """The reply of ``import_data``. *messages* maps a problem index to its text."""
    return {
        "ok": plan.ok,
        "dry_run": dry_run,
        "counts": clone(plan.counts),
        "records": clone(plan.records),
        "problems": [
            {"level": p.level, "path": p.path, "message": messages.get(i, p.key)}
            for i, p in enumerate(plan.problems)
        ],
    }


__all__ = [
    "EXCLUDED_KEYS",
    "FORMAT",
    "SECTIONS",
    "CoverJob",
    "ImportPlan",
    "Problem",
    "build_export",
    "check_files_dir",
    "cover_export_path",
    "covers_to_copy",
    "is_cover_path",
    "plan_import",
    "report",
]
