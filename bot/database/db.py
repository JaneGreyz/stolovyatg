from __future__ import annotations

import aiosqlite
from pathlib import Path

from bot.database.models import ACTIVE_STATUSES, DEFAULT_ADDRESSES, Address, Order


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self.path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._create_tables()
        await self._migrate()
        await self._seed_addresses()

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database is not connected")
        return self._connection

    async def _create_tables(self) -> None:
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL UNIQUE,
                short_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guest_id INTEGER NOT NULL,
                guest_username TEXT,
                guest_name TEXT NOT NULL,
                address TEXT NOT NULL,
                address_short TEXT NOT NULL,
                address_clarification TEXT NOT NULL DEFAULT '',
                phone TEXT NOT NULL,
                order_text TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                topic_id INTEGER,
                staff_message_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE INDEX IF NOT EXISTS idx_orders_guest_id ON orders(guest_id);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_topic_id ON orders(topic_id);
            CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);

            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        await self.conn.commit()

    async def _migrate(self) -> None:
        cursor = await self.conn.execute("PRAGMA table_info(orders)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "manager_reminder_sent" not in columns:
            await self.conn.execute(
                """
                ALTER TABLE orders
                ADD COLUMN manager_reminder_sent INTEGER NOT NULL DEFAULT 0
                """
            )
            await self.conn.commit()

        if "order_amount" not in columns:
            await self.conn.execute(
                """
                ALTER TABLE orders ADD COLUMN order_amount INTEGER
                """
            )
            await self.conn.commit()

        cursor = await self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reviews'"
        )
        if not await cursor.fetchone():
            await self.conn.execute(
                """
                CREATE TABLE reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL UNIQUE,
                    guest_id INTEGER NOT NULL,
                    rating INTEGER NOT NULL,
                    comment TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
                )
                """
            )
            await self.conn.commit()

    async def _seed_addresses(self) -> None:
        cursor = await self.conn.execute("SELECT COUNT(*) FROM addresses")
        row = await cursor.fetchone()
        if row[0] > 0:
            return

        for index, (full_name, short_name) in enumerate(DEFAULT_ADDRESSES):
            await self.conn.execute(
                """
                INSERT INTO addresses (full_name, short_name, is_active, sort_order)
                VALUES (?, ?, 1, ?)
                """,
                (full_name, short_name, index),
            )
        await self.conn.commit()

    # --- Addresses ---

    async def get_active_addresses(self) -> list[Address]:
        cursor = await self.conn.execute(
            """
            SELECT id, full_name, short_name, is_active, sort_order
            FROM addresses
            WHERE is_active = 1
            ORDER BY sort_order, id
            """
        )
        rows = await cursor.fetchall()
        return [
            Address(
                id=row["id"],
                full_name=row["full_name"],
                short_name=row["short_name"],
                is_active=bool(row["is_active"]),
                sort_order=row["sort_order"],
            )
            for row in rows
        ]

    async def get_all_addresses(self) -> list[Address]:
        cursor = await self.conn.execute(
            """
            SELECT id, full_name, short_name, is_active, sort_order
            FROM addresses
            ORDER BY sort_order, id
            """
        )
        rows = await cursor.fetchall()
        return [
            Address(
                id=row["id"],
                full_name=row["full_name"],
                short_name=row["short_name"],
                is_active=bool(row["is_active"]),
                sort_order=row["sort_order"],
            )
            for row in rows
        ]

    async def get_address_by_id(self, address_id: int) -> Address | None:
        cursor = await self.conn.execute(
            """
            SELECT id, full_name, short_name, is_active, sort_order
            FROM addresses WHERE id = ?
            """,
            (address_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return Address(
            id=row["id"],
            full_name=row["full_name"],
            short_name=row["short_name"],
            is_active=bool(row["is_active"]),
            sort_order=row["sort_order"],
        )

    async def toggle_address(self, address_id: int) -> bool | None:
        cursor = await self.conn.execute(
            "SELECT is_active FROM addresses WHERE id = ?",
            (address_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        new_value = 0 if row["is_active"] else 1
        await self.conn.execute(
            "UPDATE addresses SET is_active = ? WHERE id = ?",
            (new_value, address_id),
        )
        await self.conn.commit()
        return bool(new_value)

    # --- Orders ---

    async def create_order(
        self,
        guest_id: int,
        guest_username: str | None,
        guest_name: str,
        address: str,
        address_short: str,
        address_clarification: str,
        phone: str,
    ) -> Order:
        cursor = await self.conn.execute(
            """
            INSERT INTO orders (
                guest_id, guest_username, guest_name,
                address, address_short, address_clarification, phone
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guest_id,
                guest_username,
                guest_name,
                address,
                address_short,
                address_clarification,
                phone,
            ),
        )
        await self.conn.commit()
        order_id = cursor.lastrowid
        order = await self.get_order(order_id)
        if order is None:
            raise RuntimeError("Failed to create order")
        return order

    async def get_order(self, order_id: int) -> Order | None:
        cursor = await self.conn.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        )
        row = await cursor.fetchone()
        return Order.from_row(row) if row else None

    async def get_order_by_topic(self, topic_id: int) -> Order | None:
        cursor = await self.conn.execute(
            "SELECT * FROM orders WHERE topic_id = ?",
            (topic_id,),
        )
        row = await cursor.fetchone()
        return Order.from_row(row) if row else None

    async def get_active_order_for_guest(self, guest_id: int) -> Order | None:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        cursor = await self.conn.execute(
            f"""
            SELECT * FROM orders
            WHERE guest_id = ? AND status IN ({placeholders})
            ORDER BY id DESC LIMIT 1
            """,
            (guest_id, *ACTIVE_STATUSES),
        )
        row = await cursor.fetchone()
        return Order.from_row(row) if row else None

    async def update_order_text(self, order_id: int, order_text: str) -> None:
        await self.conn.execute(
            """
            UPDATE orders
            SET order_text = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (order_text, order_id),
        )
        await self.conn.commit()

    async def update_order_amount(self, order_id: int, order_amount: int) -> None:
        await self.conn.execute(
            """
            UPDATE orders
            SET order_amount = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (order_amount, order_id),
        )
        await self.conn.commit()

    async def update_order_status(self, order_id: int, status: str) -> None:
        await self.conn.execute(
            """
            UPDATE orders
            SET status = ?, updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (status, order_id),
        )
        await self.conn.commit()

    async def update_order_topic(
        self,
        order_id: int,
        topic_id: int,
        staff_message_id: int,
    ) -> None:
        await self.conn.execute(
            """
            UPDATE orders
            SET topic_id = ?, staff_message_id = ?,
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (topic_id, staff_message_id, order_id),
        )
        await self.conn.commit()

    async def get_orders_by_status(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Order]:
        if status:
            cursor = await self.conn.execute(
                """
                SELECT * FROM orders WHERE status = ?
                ORDER BY id DESC LIMIT ?
                """,
                (status, limit),
            )
        else:
            cursor = await self.conn.execute(
                """
                SELECT * FROM orders
                ORDER BY id DESC LIMIT ?
                """,
                (limit,),
            )
        rows = await cursor.fetchall()
        return [Order.from_row(row) for row in rows]

    async def get_orders_needing_reminder(self, minutes: int) -> list[Order]:
        cursor = await self.conn.execute(
            """
            SELECT * FROM orders
            WHERE status = 'new'
              AND topic_id IS NOT NULL
              AND manager_reminder_sent = 0
              AND datetime(created_at, ?) <= datetime('now', 'localtime')
            ORDER BY created_at ASC
            """,
            (f"+{minutes} minutes",),
        )
        rows = await cursor.fetchall()
        return [Order.from_row(row) for row in rows]

    async def mark_manager_reminder_sent(self, order_id: int) -> None:
        await self.conn.execute(
            """
            UPDATE orders
            SET manager_reminder_sent = 1,
                updated_at = datetime('now', 'localtime')
            WHERE id = ?
            """,
            (order_id,),
        )
        await self.conn.commit()

    async def get_last_completed_order_without_review(
        self, guest_id: int
    ) -> Order | None:
        cursor = await self.conn.execute(
            """
            SELECT o.* FROM orders o
            LEFT JOIN reviews r ON r.order_id = o.id
            WHERE o.guest_id = ? AND o.status = 'completed' AND r.id IS NULL
            ORDER BY o.id DESC LIMIT 1
            """,
            (guest_id,),
        )
        row = await cursor.fetchone()
        return Order.from_row(row) if row else None

    async def save_review(
        self,
        order_id: int,
        guest_id: int,
        rating: int,
        comment: str = "",
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO reviews (order_id, guest_id, rating, comment)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(order_id) DO UPDATE SET
                rating = excluded.rating,
                comment = excluded.comment,
                created_at = datetime('now', 'localtime')
            """,
            (order_id, guest_id, rating, comment),
        )
        await self.conn.commit()

    async def has_review(self, order_id: int) -> bool:
        cursor = await self.conn.execute(
            "SELECT 1 FROM reviews WHERE order_id = ?",
            (order_id,),
        )
        return await cursor.fetchone() is not None

    async def get_today_stats(self) -> dict:
        cursor = await self.conn.execute(
            """
            SELECT COUNT(*) as total FROM orders
            WHERE date(created_at) = date('now', 'localtime')
            """
        )
        total_row = await cursor.fetchone()
        total = total_row["total"]

        cursor = await self.conn.execute(
            """
            SELECT status, COUNT(*) as count FROM orders
            WHERE date(created_at) = date('now', 'localtime')
            GROUP BY status
            """
        )
        status_rows = await cursor.fetchall()
        by_status = {row["status"]: row["count"] for row in status_rows}

        cursor = await self.conn.execute(
            """
            SELECT address_short, COUNT(*) as count FROM orders
            WHERE date(created_at) = date('now', 'localtime')
            GROUP BY address_short
            ORDER BY count DESC
            """
        )
        address_rows = await cursor.fetchall()
        by_address = {row["address_short"]: row["count"] for row in address_rows}

        cursor = await self.conn.execute(
            """
            SELECT AVG(order_amount) as avg_amount, COUNT(*) as cnt
            FROM orders
            WHERE date(created_at) = date('now', 'localtime')
              AND order_amount IS NOT NULL
            """
        )
        avg_row = await cursor.fetchone()
        avg_amount = avg_row["avg_amount"]
        avg_count = avg_row["cnt"]

        return {
            "total": total,
            "by_status": by_status,
            "by_address": by_address,
            "avg_amount": round(avg_amount, 0) if avg_amount else None,
            "avg_count": avg_count,
        }

    # --- Settings ---

    async def get_setting(self, key: str) -> str | None:
        cursor = await self.conn.execute(
            "SELECT value FROM bot_settings WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO bot_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await self.conn.commit()
