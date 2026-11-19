from datetime import datetime, timezone
import pytest
from src.live_sync import build_snapshot_record
from src.sql_engine import UnsafeSQLError, validate_readonly_sql


def test_allows_tsql_select_top() -> None:
    sql = (
        "SELECT TOP 10 ticker, current_price, day_change_pct "
        "FROM live_market_snapshots ORDER BY day_change_pct DESC;"
    )
    parsed = validate_readonly_sql(sql)
    assert parsed.upper().startswith("SELECT")


@pytest.mark.parametrize(
    "bad_sql",
    [
        "DROP TABLE live_market_snapshots;",
        "DELETE FROM live_market_snapshots;",
        "UPDATE live_market_snapshots SET current_price = 0;",
        "SELECT * FROM live_market_snapshots; "
        "DROP TABLE live_market_snapshots;",
    ],
)
def test_blocks_unsafe_tsql(bad_sql: str) -> None:
    with pytest.raises(UnsafeSQLError):
        validate_readonly_sql(bad_sql)


def test_build_snapshot_record_calculates_change_pct() -> None:
    now_utc = datetime(2026, 11, 19, 10, 0, 0, tzinfo=timezone.utc)
    info = {
        "shortName": "Infosys Limited",
        "currency": "INR",
        "currentPrice": 1820.0,
        "previousClose": 1800.0,
        "volume": 2500000,
    }
    record = build_snapshot_record("INFY.NS", info, now_utc)
    assert record is not None
    assert record["ticker"] == "INFY.NS"
    assert record["day_change_pct"] == 1.11
