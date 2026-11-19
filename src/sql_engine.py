import re
from typing import Any, Dict, List, Optional, Tuple
from langchain_core.messages import HumanMessage, SystemMessage
import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from src.config import get_groq_llm, settings
from src.live_sync import LiveMarketSyncService


class UnsafeSQLError(ValueError):
    """Raised when generated SQL is not a single safe read-only SELECT
    statement.
    """


def extract_sql_candidate(raw_text: str) -> str:
    fenced = re.search(
        r"```(?:sql|tsql)?\s*(.*?)\s*```",
        raw_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return (fenced.group(1) if fenced else raw_text).strip()


def validate_readonly_sql(sql_query: str) -> str:
    """Validate T-SQL syntax and AST nodes.

    Only a single read-only SELECT query is allowed.
    """
    cleaned = extract_sql_candidate(sql_query)
    if not cleaned:
        raise UnsafeSQLError("SQL query is empty.")

    try:
        statements = sqlglot.parse(cleaned, read="tsql")
    except ParseError as exc:
        raise UnsafeSQLError(f"Invalid T-SQL syntax: {exc}") from exc

    non_empty = [stmt for stmt in statements if stmt is not None]
    if len(non_empty) != 1:
        raise UnsafeSQLError("Only a single SQL statement is allowed.")

    tree = non_empty[0]
    if not isinstance(tree, exp.Select):
        raise UnsafeSQLError(
            f"Only SELECT queries are permitted; got {type(tree).__name__}."
        )

    forbidden = (
        exp.Insert,
        exp.Update,
        exp.Delete,
        exp.Drop,
        exp.Alter,
        exp.Create,
        exp.Command,
        exp.Grant,
        exp.Revoke,
    )
    for node in tree.walk():
        if isinstance(node, forbidden):
            raise UnsafeSQLError(
                f"Disallowed SQL operation: {type(node).__name__}."
            )

    return tree.sql(dialect="tsql")


class SQLServerTextToSQLEngine:
    def __init__(self, engine: Optional[Engine] = None) -> None:
        self.engine: Engine = engine or create_engine(
            settings.mssql_uri, pool_pre_ping=True
        )
        self._table_ready = False

    def _ensure_ready(self) -> None:
        if not self._table_ready:
            LiveMarketSyncService(engine=self.engine).ensure_table()
            self._table_ready = True

    def get_schema_summary(self) -> str:
        self._ensure_ready()
        inspector = inspect(self.engine)
        tables = inspector.get_table_names()
        if not tables:
            return "No tables found."

        lines: List[str] = []
        for table_name in tables:
            cols = ", ".join(
                f"{col['name']} ({col['type']})"
                for col in inspector.get_columns(table_name)
            )
            lines.append(f"- `{table_name}`: {cols}")
        return "\n".join(lines)

    def generate_sql(self, question: str) -> str:
        schema = self.get_schema_summary()
        llm = get_groq_llm(temperature=0.0)
        system_prompt = (
            "Generate one valid read-only Microsoft SQL Server (T-SQL) SELECT "
            "query using ONLY this schema:\n"
            f"{schema}\n\n"
            "Rules:\n"
            "1. Output ONLY raw T-SQL with no markdown fences or notes.\n"
            "2. Never write INSERT, UPDATE, DELETE, DROP, ALTER, or MERGE.\n"
            "3. Use TOP 50 after SELECT unless aggregating with GROUP BY."
        )
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=question),
            ]
        )
        raw_sql = (
            response.content
            if isinstance(response.content, str)
            else str(response.content)
        )
        return validate_readonly_sql(raw_sql)

    def execute_question(
        self, question: str
    ) -> Tuple[str, List[Dict[str, Any]]]:
        safe_sql = self.generate_sql(question)
        with self.engine.connect() as conn:
            result = conn.execute(text(safe_sql))
            rows = [dict(row._mapping) for row in result]
        return safe_sql, rows
