"""One SQLite transaction across all models, so state and its timeline event commit together.

Every model persists as its JSON in one table. Changing a model needs no migration,
unless stored data no longer loads: then bump STORE_VERSION, which rebuilds the
database from the seed on the next start and discards what's there.
"""

import sqlite3
from pathlib import Path
from types import TracebackType
from typing import Self

from grok_invoices.domain.errors import NotFound
from grok_invoices.domain.models import Case, Client, Entity, Event, Invoice, Posting, Question
from grok_invoices.settings import get_settings

STORE_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
    kind TEXT NOT NULL,
    id INTEGER NOT NULL,
    data TEXT NOT NULL,
    PRIMARY KEY (kind, id)
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS sequences (
    kind TEXT PRIMARY KEY,
    value INTEGER NOT NULL
) WITHOUT ROWID;
"""


def _db_path() -> Path:
    return get_settings().data_dir / "platform.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_store() -> None:
    """Create the store, or rebuild it if it was written by an older STORE_VERSION."""
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    conn = _connect()
    try:
        if conn.execute("PRAGMA user_version").fetchone()[0] != STORE_VERSION:
            # Earlier releases used other tables here. Everything in this file is demo data.
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall():
                conn.execute(f'DROP TABLE IF EXISTS "{row["name"]}"')
            conn.executescript(_SCHEMA)
            conn.execute(f"PRAGMA user_version = {STORE_VERSION}")
        conn.execute("PRAGMA journal_mode = WAL")
    finally:
        conn.close()


class Repository[T: Entity]:
    """Entities you load or add are saved when the transaction commits, so a save can't be forgotten."""

    def __init__(self, conn: sqlite3.Connection, model: type[T]) -> None:
        self._conn = conn
        self._model = model
        self._kind = model.__name__
        self._seen: dict[int, T] = {}

    def _track(self, row: sqlite3.Row) -> T:
        entity = self._seen.get(row["id"])
        if entity is None:
            entity = self._model.model_validate_json(row["data"])
            self._seen[entity.id] = entity
        return entity

    def get(self, id_: int) -> T | None:
        row = self._conn.execute("SELECT id, data FROM entities WHERE kind = ? AND id = ?", (self._kind, id_)).fetchone()
        return self._track(row) if row else None

    def require(self, id_: int) -> T:
        entity = self.get(id_)
        if entity is None:
            raise NotFound(f"{self._kind} {id_} not found")
        return entity

    def all(self) -> list[T]:
        rows = self._conn.execute("SELECT id, data FROM entities WHERE kind = ? ORDER BY id", (self._kind,)).fetchall()
        return [self._track(row) for row in rows]

    def after(self, id_: int, limit: int) -> list[T]:
        rows = self._conn.execute(
            "SELECT id, data FROM entities WHERE kind = ? AND id > ? ORDER BY id LIMIT ?", (self._kind, id_, limit)
        ).fetchall()
        return [self._track(row) for row in rows]

    def add(self, entity: T) -> T:
        entity.id = self._conn.execute(
            "INSERT INTO sequences (kind, value) VALUES (?, 1)"
            " ON CONFLICT (kind) DO UPDATE SET value = value + 1 RETURNING value",
            (self._kind,),
        ).fetchone()[0]
        self._conn.execute(
            "INSERT INTO entities (kind, id, data) VALUES (?, ?, ?)", (self._kind, entity.id, entity.model_dump_json())
        )
        self._seen[entity.id] = entity
        return entity

    def flush(self) -> None:
        for entity in self._seen.values():
            self._conn.execute(
                "UPDATE entities SET data = ? WHERE kind = ? AND id = ?", (entity.model_dump_json(), self._kind, entity.id)
            )


class UnitOfWork:
    """Commits when the block ends normally and rolls back on any exception.

    Keep network calls outside the block: a write transaction blocks all other writers.
    """

    def __init__(self, write: bool = True) -> None:
        self._write = write

    def __enter__(self) -> Self:
        self._conn = _connect()
        self._conn.execute("BEGIN IMMEDIATE" if self._write else "BEGIN")
        self.clients = Repository(self._conn, Client)
        self.invoices = Repository(self._conn, Invoice)
        self.postings = Repository(self._conn, Posting)
        self.cases = Repository(self._conn, Case)
        self.questions = Repository(self._conn, Question)
        self.events = Repository(self._conn, Event)
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        try:
            if exc_type is None and self._write:
                for repository in (self.clients, self.invoices, self.postings, self.cases, self.questions, self.events):
                    repository.flush()
                self._conn.execute("COMMIT")
            else:
                self._conn.execute("ROLLBACK")
        finally:
            self._conn.close()

    @property
    def client(self) -> Client:
        return self.clients.require(1)

    def clear_for_reset(self) -> None:
        """Remove all state. Event ids keep counting so a timeline reader's cursor stays valid."""
        self._conn.execute("DELETE FROM entities")
        self._conn.execute("DELETE FROM sequences WHERE kind != ?", (Event.__name__,))
        for repository in (self.clients, self.invoices, self.postings, self.cases, self.questions, self.events):
            repository._seen.clear()
