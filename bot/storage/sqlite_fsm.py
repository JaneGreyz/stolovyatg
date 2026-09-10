from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite
from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StateType, StorageKey


class SQLiteFSMStorage(BaseStorage):
    """Persist FSM state in SQLite so checkout survives restarts and multi-process setups."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._conn: aiosqlite.Connection | None = None

    async def _get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(self.database_path, timeout=30)
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS fsm_states (
                    key TEXT PRIMARY KEY,
                    state TEXT,
                    data TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            await self._conn.commit()
        return self._conn

    @staticmethod
    def _storage_key(key: StorageKey) -> str:
        return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.destiny}"

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        conn = await self._get_conn()
        storage_key = self._storage_key(key)
        state_value = state.state if isinstance(state, State) else state
        cursor = await conn.execute(
            "SELECT 1 FROM fsm_states WHERE key = ?",
            (storage_key,),
        )
        exists = await cursor.fetchone()
        if exists:
            await conn.execute(
                "UPDATE fsm_states SET state = ? WHERE key = ?",
                (state_value, storage_key),
            )
        else:
            await conn.execute(
                "INSERT INTO fsm_states (key, state, data) VALUES (?, ?, '{}')",
                (storage_key, state_value),
            )
        await conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT state FROM fsm_states WHERE key = ?",
            (self._storage_key(key),),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        conn = await self._get_conn()
        storage_key = self._storage_key(key)
        payload = json.dumps(data, ensure_ascii=False)
        cursor = await conn.execute(
            "SELECT 1 FROM fsm_states WHERE key = ?",
            (storage_key,),
        )
        exists = await cursor.fetchone()
        if exists:
            await conn.execute(
                "UPDATE fsm_states SET data = ? WHERE key = ?",
                (payload, storage_key),
            )
        else:
            await conn.execute(
                "INSERT INTO fsm_states (key, state, data) VALUES (?, NULL, ?)",
                (storage_key, payload),
            )
        await conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        conn = await self._get_conn()
        cursor = await conn.execute(
            "SELECT data FROM fsm_states WHERE key = ?",
            (self._storage_key(key),),
        )
        row = await cursor.fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return {}
