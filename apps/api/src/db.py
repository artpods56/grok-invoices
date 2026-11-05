"""SQLite storage for the platform. All state lives in one file under DATA_DIR."""

import os
import sqlite3
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE client (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL,
    nip TEXT NOT NULL
);
CREATE TABLE vehicles (
    plate TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    usage TEXT NOT NULL CHECK (usage IN ('company', 'mixed', 'private'))
);
CREATE TABLE client_facts (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE accounts (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    ksef_number TEXT NOT NULL UNIQUE,
    seller_name TEXT NOT NULL,
    seller_nip TEXT NOT NULL,
    description TEXT NOT NULL,
    vehicle_plate TEXT,
    net TEXT NOT NULL,
    vat TEXT NOT NULL,
    gross TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('received', 'escalated', 'posted')),
    received_at TEXT NOT NULL
);
CREATE TABLE cases (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices (id),
    status TEXT NOT NULL CHECK (status IN ('open', 'waiting_for_client', 'resolved')),
    reason TEXT NOT NULL,
    opened_by TEXT NOT NULL,
    assignee TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE TABLE postings (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices (id),
    case_id INTEGER REFERENCES cases (id),
    account TEXT NOT NULL REFERENCES accounts (code),
    vat_deduction_percent INTEGER NOT NULL,
    rationale TEXT NOT NULL,
    confidence REAL NOT NULL,
    actor TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('rule', 'precedent', 'regulation', 'accountant')),
    precedent_id INTEGER REFERENCES postings (id),
    legal_basis TEXT,
    reusable INTEGER NOT NULL,
    conditions TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'superseded')),
    superseded_by INTEGER REFERENCES postings (id),
    created_at TEXT NOT NULL
);
CREATE TABLE questions (
    id INTEGER PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES cases (id),
    text TEXT NOT NULL,
    asked_by TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'answered')),
    answer TEXT,
    answered_by TEXT,
    created_at TEXT NOT NULL,
    answered_at TEXT
);
CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    type TEXT NOT NULL,
    summary TEXT NOT NULL,
    invoice_id INTEGER,
    case_id INTEGER,
    data TEXT NOT NULL
);
"""

# The database only holds demo data, so a schema change rebuilds it from the seed.
# Revisit this before storing anything that can't be recreated.
SCHEMA_VERSION = zlib.crc32(SCHEMA.encode()) & 0x7FFFFFFF

TABLES = (
    "events", "questions", "postings", "cases", "invoices",
    "accounts", "client_facts", "vehicles", "client",
)


def db_path() -> Path:
    return Path(os.environ.get("DATA_DIR", ".data")) / "platform.sqlite3"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version == SCHEMA_VERSION:
            return
        conn.execute("PRAGMA foreign_keys = OFF")
        for table in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        conn.execute("PRAGMA journal_mode = WAL")
    finally:
        conn.close()


@contextmanager
def read() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Run one write atomically, so state and its timeline event commit together."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
