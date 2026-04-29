import aiosqlite

from manicure_bot.config import DB_PATH


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS working_days (
    date TEXT PRIMARY KEY,                         -- YYYY-MM-DD
    is_closed INTEGER NOT NULL DEFAULT 0,        -- 0 - open, 1 - closed
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS time_slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                           -- YYYY-MM-DD
    time TEXT NOT NULL,                           -- HH:MM
    UNIQUE(date, time),
    FOREIGN KEY (date) REFERENCES working_days(date) ON DELETE CASCADE
);

-- status: active - booked, cancelled - freed
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    slot_id INTEGER NOT NULL,
    booking_date TEXT NOT NULL,                   -- YYYY-MM-DD
    booking_time TEXT NOT NULL,                   -- HH:MM
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active','cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    cancelled_at TEXT,
    FOREIGN KEY (slot_id) REFERENCES time_slots(id) ON DELETE RESTRICT
);

-- One active booking per time slot
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_booking_per_slot
ON bookings(slot_id) WHERE status='active';

-- One active booking per user (requirement: no multiple dates simultaneously)
CREATE UNIQUE INDEX IF NOT EXISTS ux_active_booking_per_user
ON bookings(user_id) WHERE status='active';

CREATE TABLE IF NOT EXISTS reminder_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE,
    run_at TEXT NOT NULL,                        -- ISO datetime
    job_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','sent','cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    sent_at TEXT,
    cancelled_at TEXT,
    FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
);
"""


class Database:
    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path

    async def init(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA_SQL)
            await db.commit()

    async def execute(self, sql: str, params: tuple = ()) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(sql, params)
            await db.commit()

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, params)
            row = await cur.fetchone()
            return dict(row) if row else None

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def run_in_transaction(self, fn) -> any:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            try:
                result = await fn(db)
                await db.commit()
                return result
            except Exception:
                await db.rollback()
                raise

