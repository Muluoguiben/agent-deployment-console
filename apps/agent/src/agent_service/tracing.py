"""Step-level trace recording. Every graph-node execution writes a row the console can read."""

import json
import sqlite3
import time
import uuid


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class RunRecorder:
    def __init__(
        self,
        conn: sqlite3.Connection,
        version_id: int,
        conversation_id: str | None,
        user_message: str,
        source: str = "chat",
    ):
        self.conn = conn
        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self._t0 = _now_ms()
        self._idx = 0
        conn.execute(
            """INSERT INTO runs (id, conversation_id, version_id, user_message, source)
               VALUES (?, ?, ?, ?, ?)""",
            (self.run_id, conversation_id, version_id, user_message, source),
        )
        conn.commit()

    def step(self, kind: str, name: str, input_obj, output_obj, latency_ms: int | None = None):
        self.conn.execute(
            """INSERT INTO steps (run_id, idx, kind, name, input_json, output_json, latency_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                self.run_id,
                self._idx,
                kind,
                name,
                json.dumps(input_obj, ensure_ascii=False, default=str)[:20000],
                json.dumps(output_obj, ensure_ascii=False, default=str)[:20000],
                latency_ms,
            ),
        )
        self.conn.commit()
        self._idx += 1

    def finish(self, status: str, final_text: str, input_tokens: int, output_tokens: int):
        self.conn.execute(
            """UPDATE runs SET finished_at=datetime('now'), status=?, final_text=?,
               latency_ms=?, input_tokens=?, output_tokens=? WHERE id=?""",
            (status, final_text, _now_ms() - self._t0, input_tokens, output_tokens, self.run_id),
        )
        self.conn.commit()
