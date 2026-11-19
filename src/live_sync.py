from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import yfinance as yf
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from src.config import settings

CREATE_MARKET_TABLE_SQL = """
IF OBJECT_ID('dbo.live_market_snapshots', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.live_market_snapshots (
        ticker NVARCHAR(32) NOT NULL PRIMARY KEY,
        company_name NVARCHAR(128) NOT NULL,
        currency NVARCHAR(16) NOT NULL,
        current_price FLOAT NOT NULL,
        previous_close FLOAT NULL,
        day_change_pct FLOAT NULL,
        day_volume BIGINT NULL,
        synced_at_utc DATETIME2 NOT NULL
    );
END
"""

MERGE_MARKET_ROW_SQL = """
MERGE dbo.live_market_snapshots AS target
USING (
    SELECT
        CAST(:ticker AS NVARCHAR(32)) AS ticker,
        CAST(:company_name AS NVARCHAR(128)) AS company_name,
        CAST(:currency AS NVARCHAR(16)) AS currency,
        CAST(:current_price AS FLOAT) AS current_price,
        CAST(:previous_close AS FLOAT) AS previous_close,
        CAST(:day_change_pct AS FLOAT) AS day_change_pct,
        CAST(:day_volume AS BIGINT) AS day_volume,
        CAST(:synced_at_utc AS DATETIME2) AS synced_at_utc
) AS source
ON target.ticker = source.ticker
WHEN MATCHED THEN
    UPDATE SET
        company_name = source.company_name,
        currency = source.currency,
        current_price = source.current_price,
        previous_close = source.previous_close,
        day_change_pct = source.day_change_pct,
        day_volume = source.day_volume,
        synced_at_utc = source.synced_at_utc
WHEN NOT MATCHED THEN
    INSERT (
        ticker,
        company_name,
        currency,
        current_price,
        previous_close,
        day_change_pct,
        day_volume,
        synced_at_utc
    )
    VALUES (
        source.ticker,
        source.company_name,
        source.currency,
        source.current_price,
        source.previous_close,
        source.day_change_pct,
        source.day_volume,
        source.synced_at_utc
    );
"""


def build_snapshot_record(
    ticker: str,
    info: Dict[str, Any],
    synced_at_utc: datetime,
) -> Optional[Dict[str, Any]]:
    """Normalize live ticker fields safely against missing API keys."""
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        return None

    prev_close = info.get("previousClose") or info.get(
        "regularMarketPreviousClose"
    )
    change_pct: Optional[float] = None
    if prev_close and float(prev_close) != 0:
        change_pct = round(
            ((float(price) - float(prev_close)) / float(prev_close)) * 100.0, 2
        )

    volume_raw = info.get("volume") or info.get("regularMarketVolume")
    volume_val = int(volume_raw) if volume_raw is not None else 0

    company_name = str(
        info.get("shortName") or info.get("longName") or ticker
    ).strip()[:128]
    currency = str(info.get("currency") or "USD").strip()[:16]

    return {
        "ticker": ticker.upper(),
        "company_name": company_name,
        "currency": currency,
        "current_price": round(float(price), 4),
        "previous_close": (
            round(float(prev_close), 4) if prev_close is not None else None
        ),
        "day_change_pct": change_pct,
        "day_volume": volume_val,
        "synced_at_utc": synced_at_utc.replace(tzinfo=None),
    }


class LiveMarketSyncService:
    def __init__(self, engine: Optional[Engine] = None) -> None:
        self.engine: Engine = engine or create_engine(
            settings.mssql_uri, pool_pre_ping=True
        )

    def ensure_table(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text(CREATE_MARKET_TABLE_SQL))

    def sync_tickers(
        self, tickers: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        self.ensure_table()
        target_tickers = [
            t.strip().upper()
            for t in (tickers or settings.live_tickers)
            if t.strip()
        ]
        synced_time = datetime.now(timezone.utc)

        synced_rows: List[Dict[str, Any]] = []
        failed_tickers: List[str] = []

        for symbol in target_tickers:
            try:
                info_dict = yf.Ticker(symbol).info or {}
                record = build_snapshot_record(symbol, info_dict, synced_time)
                if record is None:
                    failed_tickers.append(symbol)
                    continue
                synced_rows.append(record)
            except Exception:
                failed_tickers.append(symbol)

        if synced_rows:
            with self.engine.begin() as conn:
                for row in synced_rows:
                    conn.execute(text(MERGE_MARKET_ROW_SQL), row)

        return {
            "synced_count": len(synced_rows),
            "failed_tickers": failed_tickers,
            "synced_at_utc": synced_time.isoformat(),
        }

    def get_latest_sync_time(self) -> Optional[str]:
        self.ensure_table()
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    text(
                        "SELECT MAX(synced_at_utc) AS last_sync "
                        "FROM live_market_snapshots"
                    )
                )
                .mappings()
                .first()
            )
        if not row or row["last_sync"] is None:
            return None
        return str(row["last_sync"])
