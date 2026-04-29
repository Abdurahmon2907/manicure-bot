from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from manicure_bot.database.db import Database


@dataclass(slots=True)
class BookingInfo:
    booking_id: int
    user_id: int
    booking_date: str
    booking_time: str
    name: str
    phone: str


def utc_now_iso() -> str:
    # SQLite stores ISO datetime as TEXT; keep it consistent for APScheduler restore
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class Repository:
    def __init__(self, db: Database) -> None:
        self.db = db

    async def add_working_day(self, date: str) -> None:
        await self.db.execute(
            """
            INSERT OR IGNORE INTO working_days(date, is_closed)
            VALUES(?, 0)
            """,
            (date,),
        )
        # If the day already exists (e.g. was closed) - reopen it.
        await self.db.execute(
            "UPDATE working_days SET is_closed=0 WHERE date=?",
            (date,),
        )

    async def close_day(self, date: str) -> None:
        await self.db.execute(
            """
            INSERT OR IGNORE INTO working_days(date, is_closed)
            VALUES(?, 1)
            """,
            (date,),
        )
        await self.db.execute(
            "UPDATE working_days SET is_closed=1 WHERE date=?",
            (date,),
        )

    async def is_day_closed(self, date: str) -> bool:
        row = await self.db.fetchone(
            "SELECT is_closed FROM working_days WHERE date=?",
            (date,),
        )
        return bool(row and row["is_closed"] == 1)

    async def add_time_slot(self, date: str, time: str) -> None:
        # Ensure working day exists
        await self.add_working_day(date)
        await self.db.execute(
            """
            INSERT OR IGNORE INTO time_slots(date, time)
            VALUES(?, ?)
            """,
            (date, time),
        )

    async def delete_time_slot(self, date: str, time: str) -> None:
        await self.db.execute(
            "DELETE FROM time_slots WHERE date=? AND time=?",
            (date, time),
        )

    async def get_time_slot_id(self, date: str, time: str) -> int | None:
        row = await self.db.fetchone(
            "SELECT id FROM time_slots WHERE date=? AND time=?",
            (date, time),
        )
        return int(row["id"]) if row else None

    async def get_free_slots(self, date: str) -> list[dict]:
        # Free = slot exists AND no active booking for this slot
        rows = await self.db.fetchall(
            """
            SELECT ts.id, ts.time
            FROM time_slots ts
            JOIN working_days wd ON wd.date=ts.date AND wd.is_closed=0
            WHERE ts.date=?
              AND NOT EXISTS (
                SELECT 1 FROM bookings b
                WHERE b.slot_id=ts.id AND b.status='active'
              )
            ORDER BY ts.time
            """,
            (date,),
        )
        return rows

    async def get_free_slots_count_by_date(self, date_from: str, date_to: str) -> dict[str, int]:
        rows = await self.db.fetchall(
            """
            SELECT ts.date, COUNT(*) as free_count
            FROM time_slots ts
            JOIN working_days wd ON wd.date=ts.date AND wd.is_closed=0
            LEFT JOIN bookings b
              ON b.slot_id=ts.id AND b.status='active'
            WHERE wd.date BETWEEN ? AND ?
              AND b.id IS NULL
            GROUP BY ts.date
            """,
            (date_from, date_to),
        )
        return {r["date"]: int(r["free_count"]) for r in rows}

    async def get_available_month_days(
        self,
        month_start: str,
        month_end: str,
    ) -> set[str]:
        counts = await self.get_free_slots_count_by_date(month_start, month_end)
        return {d for d, c in counts.items() if c > 0}

    async def get_schedule_for_admin(self, date: str) -> list[dict]:
        rows = await self.db.fetchall(
            """
            SELECT
                ts.id as slot_id,
                ts.time,
                b.user_id,
                b.name,
                b.phone
            FROM time_slots ts
            LEFT JOIN bookings b
              ON b.slot_id=ts.id AND b.status='active'
            WHERE ts.date=?
            ORDER BY ts.time
            """,
            (date,),
        )
        return rows

    async def get_active_booking_for_user(self, user_id: int) -> BookingInfo | None:
        row = await self.db.fetchone(
            """
            SELECT b.id as booking_id, b.user_id, b.booking_date, b.booking_time, b.name, b.phone
            FROM bookings b
            WHERE b.user_id=? AND b.status='active'
            LIMIT 1
            """,
            (user_id,),
        )
        if not row:
            return None
        return BookingInfo(
            booking_id=int(row["booking_id"]),
            user_id=int(row["user_id"]),
            booking_date=row["booking_date"],
            booking_time=row["booking_time"],
            name=row["name"],
            phone=row["phone"],
        )

    async def get_booking_by_id(self, booking_id: int) -> BookingInfo | None:
        row = await self.db.fetchone(
            """
            SELECT id as booking_id, user_id, booking_date, booking_time, name, phone
            FROM bookings
            WHERE id=?
            """,
            (booking_id,),
        )
        if not row:
            return None
        return BookingInfo(
            booking_id=int(row["booking_id"]),
            user_id=int(row["user_id"]),
            booking_date=row["booking_date"],
            booking_time=row["booking_time"],
            name=row["name"],
            phone=row["phone"],
        )

    async def create_booking(
        self,
        user_id: int,
        date: str,
        time: str,
        name: str,
        phone: str,
    ) -> tuple[int, int | None]:
        """
        Returns (booking_id, reminder_job_id_numeric_part or None).
        """
        now_slot_id = await self.get_time_slot_id(date, time)
        if now_slot_id is None:
            raise ValueError("Выбранный слот недоступен.")

        # Prevent multiple active bookings per user
        active = await self.db.fetchone(
            "SELECT 1 FROM bookings WHERE user_id=? AND status='active' LIMIT 1",
            (user_id,),
        )
        if active:
            raise ValueError("У вас уже есть активная запись. Сначала отмените её.")

        # Ensure slot is not booked and day is open atomically
        async def _tx(db):
            # Check day open
            cur_day = await db.execute(
                "SELECT is_closed FROM working_days WHERE date=?",
                (date,),
            )
            day = await cur_day.fetchone()
            if not day or int(day["is_closed"]) == 1:
                raise ValueError("Этот день закрыт для записи.")

            # Check slot still free
            cur_slot = await db.execute(
                """
                SELECT ts.id
                FROM time_slots ts
                LEFT JOIN bookings b
                  ON b.slot_id=ts.id AND b.status='active'
                WHERE ts.id=? AND b.id IS NULL
                """,
                (now_slot_id,),
            )
            slot = await cur_slot.fetchone()
            if not slot:
                raise ValueError("К сожалению, слот уже занят. Попробуйте другой.")

            cur = await db.execute(
                """
                INSERT INTO bookings(user_id, slot_id, booking_date, booking_time, name, phone, status)
                VALUES(?, ?, ?, ?, ?, ?, 'active')
                """,
                (user_id, now_slot_id, date, time, name, phone),
            )
            booking_id = int(cur.lastrowid)
            return booking_id

        booking_id = await self.db.run_in_transaction(_tx)

        return booking_id, None

    async def cancel_booking(self, booking_id: int) -> tuple[int, str | None]:
        """
        Returns (booking_id, removed_job_id) where removed_job_id might be None.
        """
        # We need job_id for scheduler deletion
        row = await self.db.fetchone(
            "SELECT job_id FROM reminder_jobs WHERE booking_id=? AND status='scheduled' LIMIT 1",
            (booking_id,),
        )
        removed_job_id = str(row["job_id"]) if row else None

        await self.db.execute(
            """
            UPDATE bookings
            SET status='cancelled', cancelled_at=datetime('now','localtime')
            WHERE id=? AND status='active'
            """,
            (booking_id,),
        )
        await self.db.execute(
            """
            UPDATE reminder_jobs
            SET status='cancelled', cancelled_at=datetime('now','localtime')
            WHERE booking_id=? AND status='scheduled'
            """,
            (booking_id,),
        )
        return booking_id, removed_job_id

    async def list_bookings_for_date(self, date: str) -> list[dict]:
        rows = await self.db.fetchall(
            """
            SELECT
                b.id as booking_id,
                b.booking_time,
                b.name,
                b.phone,
                b.user_id
            FROM bookings b
            WHERE b.booking_date=? AND b.status='active'
            ORDER BY b.booking_time
            """,
            (date,),
        )
        return rows

    async def create_reminder_job_record(
        self,
        booking_id: int,
        run_at_iso: str,
        job_id: str,
    ) -> None:
        await self.db.execute(
            """
            INSERT INTO reminder_jobs(booking_id, run_at, job_id, status)
            VALUES(?, ?, ?, 'scheduled')
            """,
            (booking_id, run_at_iso, job_id),
        )

    async def get_scheduled_reminders_after(self, now_iso: str) -> list[dict]:
        return await self.db.fetchall(
            """
            SELECT booking_id, run_at, job_id
            FROM reminder_jobs
            WHERE status='scheduled' AND run_at > ?
            ORDER BY run_at
            """,
            (now_iso,),
        )

    async def mark_reminder_sent(self, booking_id: int) -> None:
        await self.db.execute(
            """
            UPDATE reminder_jobs
            SET status='sent', sent_at=datetime('now','localtime')
            WHERE booking_id=? AND status='scheduled'
            """,
            (booking_id,),
        )

    async def mark_reminder_cancelled(self, booking_id: int) -> None:
        await self.db.execute(
            """
            UPDATE reminder_jobs
            SET status='cancelled', cancelled_at=datetime('now','localtime')
            WHERE booking_id=? AND status='scheduled'
            """,
            (booking_id,),
        )

    async def get_booking_date_time_by_id(self, booking_id: int) -> tuple[str, str] | None:
        row = await self.db.fetchone(
            "SELECT booking_date, booking_time FROM bookings WHERE id=?",
            (booking_id,),
        )
        if not row:
            return None
        return row["booking_date"], row["booking_time"]

    async def is_booking_active(self, booking_id: int) -> bool:
        row = await self.db.fetchone(
            "SELECT 1 FROM bookings WHERE id=? AND status='active' LIMIT 1",
            (booking_id,),
        )
        return bool(row)

