from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import (
    Account,
    AdvisorCards,
    AdvisorOutput,
    AgentRun,
    Balance,
    Metrics,
    Position,
    Snapshot,
)
from .security import ensure_private_directory, ensure_private_file

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    account_no TEXT NOT NULL,
    product_code TEXT NOT NULL,
    kis_appkey_ref TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    balance_json TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    market_context_json TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES accounts(id)
);

CREATE TABLE IF NOT EXISTS advisor_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    snapshot_id INTEGER,
    ts TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_git_ref TEXT NOT NULL,
    tool_calls_json TEXT NOT NULL,
    summary TEXT NOT NULL,
    risks_json TEXT NOT NULL,
    watchlist_json TEXT NOT NULL,
    token_usage_json TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES accounts(id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    snapshot_id INTEGER,
    ts TEXT NOT NULL,
    role TEXT NOT NULL,
    model TEXT NOT NULL,
    input_json TEXT NOT NULL,
    output_markdown TEXT NOT NULL,
    token_usage_json TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES accounts(id),
    FOREIGN KEY(snapshot_id) REFERENCES snapshots(id)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    ensure_private_directory(db_path.parent)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_private_file(db_path)
    return conn


def init_db(db_path: Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


def upsert_account(db_path: Path, account: Account) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO accounts
                (id, label, account_no, product_code, kis_appkey_ref, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                label=excluded.label,
                account_no=excluded.account_no,
                product_code=excluded.product_code,
                kis_appkey_ref=excluded.kis_appkey_ref,
                is_active=excluded.is_active
            """,
            (
                account.id,
                account.label,
                account.account_no,
                account.product_code,
                account.kis_appkey_ref,
                1 if account.is_active else 0,
                account.created_at.isoformat(),
            ),
        )


def list_accounts(db_path: Path) -> list[Account]:
    init_db(db_path)
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM accounts ORDER BY created_at ASC").fetchall()
    return [
        Account(
            id=row["id"],
            label=row["label"],
            account_no=row["account_no"],
            product_code=row["product_code"],
            kis_appkey_ref=row["kis_appkey_ref"],
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def active_account(db_path: Path) -> Account | None:
    accounts = [account for account in list_accounts(db_path) if account.is_active]
    return accounts[0] if accounts else None


def set_active_account(db_path: Path, account_id: str) -> None:
    init_db(db_path)
    with connect(db_path) as conn:
        found = conn.execute("SELECT id FROM accounts WHERE id = ?", (account_id,)).fetchone()
        if not found:
            raise ValueError(f"Unknown account id: {account_id}")
        conn.execute("UPDATE accounts SET is_active = 0")
        conn.execute("UPDATE accounts SET is_active = 1 WHERE id = ?", (account_id,))


def _balance_to_json(balance: Balance) -> dict[str, Any]:
    return {
        "account_id": balance.account_id,
        "ts": balance.ts.isoformat(),
        "cash": balance.cash,
        "eval_total": balance.eval_total,
        "pnl_total": balance.pnl_total,
        "positions": [asdict(position) for position in balance.positions],
    }


def _metrics_to_json(metrics: Metrics) -> dict[str, Any]:
    return {
        "hhi": metrics.hhi,
        "sector_dist": metrics.sector_dist,
        "top_n_pct": metrics.top_n_pct,
        "position_weights": metrics.position_weights,
    }


def save_snapshot(db_path: Path, snapshot: Snapshot) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO snapshots
                (account_id, ts, balance_json, metrics_json, market_context_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                snapshot.account_id,
                snapshot.ts.isoformat(),
                json.dumps(_balance_to_json(snapshot.balance), ensure_ascii=False),
                json.dumps(_metrics_to_json(snapshot.metrics), ensure_ascii=False),
                json.dumps(snapshot.market_context, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def latest_snapshot(db_path: Path, account_id: str) -> Snapshot | None:
    init_db(db_path)
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE account_id = ? ORDER BY ts DESC LIMIT 1",
            (account_id,),
        ).fetchone()
    if row is None:
        return None
    balance_raw = json.loads(row["balance_json"])
    metrics_raw = json.loads(row["metrics_json"])
    balance = Balance(
        account_id=balance_raw["account_id"],
        ts=datetime.fromisoformat(balance_raw["ts"]),
        cash=float(balance_raw["cash"]),
        eval_total=float(balance_raw["eval_total"]),
        pnl_total=float(balance_raw["pnl_total"]),
        positions=[Position(**position) for position in balance_raw["positions"]],
    )
    metrics = Metrics(**metrics_raw)
    return Snapshot(
        id=int(row["id"]),
        account_id=row["account_id"],
        ts=datetime.fromisoformat(row["ts"]),
        balance=balance,
        metrics=metrics,
        market_context=json.loads(row["market_context_json"]),
    )


def save_advisor_output(db_path: Path, output: AdvisorOutput) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO advisor_outputs
                (account_id, snapshot_id, ts, model, prompt_git_ref, tool_calls_json,
                 summary, risks_json, watchlist_json, token_usage_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                output.account_id,
                output.snapshot_id,
                output.ts.isoformat(),
                output.model,
                output.prompt_git_ref,
                json.dumps(output.tool_calls, ensure_ascii=False),
                output.cards.summary,
                json.dumps(output.cards.risks, ensure_ascii=False),
                json.dumps(output.cards.watchlist, ensure_ascii=False),
                json.dumps(output.token_usage, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def list_advisor_outputs(
    db_path: Path, account_id: str | None = None, limit: int = 20
) -> list[AdvisorOutput]:
    init_db(db_path)
    query = "SELECT * FROM advisor_outputs"
    params: list[Any] = []
    if account_id:
        query += " WHERE account_id = ?"
        params.append(account_id)
    query += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        AdvisorOutput(
            id=int(row["id"]),
            account_id=row["account_id"],
            snapshot_id=int(row["snapshot_id"]) if row["snapshot_id"] is not None else None,
            ts=datetime.fromisoformat(row["ts"]),
            model=row["model"],
            prompt_git_ref=row["prompt_git_ref"],
            tool_calls=json.loads(row["tool_calls_json"]),
            cards=AdvisorCards(
                summary=row["summary"],
                risks=json.loads(row["risks_json"]),
                watchlist=json.loads(row["watchlist_json"]),
            ),
            token_usage=json.loads(row["token_usage_json"]),
        )
        for row in rows
    ]


def save_agent_run(db_path: Path, run: AgentRun) -> int:
    init_db(db_path)
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_runs
                (account_id, snapshot_id, ts, role, model, input_json,
                 output_markdown, token_usage_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run.account_id,
                run.snapshot_id,
                run.ts.isoformat(),
                run.role,
                run.model,
                json.dumps(run.input_json, ensure_ascii=False),
                run.output_markdown,
                json.dumps(run.token_usage, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)


def list_agent_runs(
    db_path: Path,
    account_id: str | None = None,
    snapshot_id: int | None = None,
    limit: int = 50,
) -> list[AgentRun]:
    init_db(db_path)
    query = "SELECT * FROM agent_runs"
    clauses: list[str] = []
    params: list[Any] = []
    if account_id:
        clauses.append("account_id = ?")
        params.append(account_id)
    if snapshot_id is not None:
        clauses.append("snapshot_id = ?")
        params.append(snapshot_id)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY ts ASC, id ASC LIMIT ?"
    params.append(limit)
    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        AgentRun(
            id=int(row["id"]),
            account_id=row["account_id"],
            snapshot_id=int(row["snapshot_id"]) if row["snapshot_id"] is not None else None,
            ts=datetime.fromisoformat(row["ts"]),
            role=row["role"],
            model=row["model"],
            input_json=json.loads(row["input_json"]),
            output_markdown=row["output_markdown"],
            token_usage=json.loads(row["token_usage_json"]),
        )
        for row in rows
    ]
