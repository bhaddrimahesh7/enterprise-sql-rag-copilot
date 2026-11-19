import os
from dataclasses import dataclass
from typing import List
from urllib.parse import quote_plus
from dotenv import load_dotenv
from pydantic import SecretStr

load_dotenv()


def _parse_tickers(raw_tickers: str) -> List[str]:
    items = [
        token.strip().upper()
        for token in raw_tickers.split(",")
        if token.strip()
    ]
    return items or ["RELIANCE.NS", "TCS.NS", "AAPL", "MSFT"]


@dataclass(frozen=True)
class Settings:
    groq_api_key: str = os.getenv("GROQ_API_KEY", "").strip()
    groq_model_name: str = os.getenv(
        "GROQ_MODEL_NAME", "llama-3.3-70b-versatile"
    ).strip()
    live_tickers_raw: str = os.getenv(
        "LIVE_TICKERS", "RELIANCE.NS,TCS.NS,INFY.NS,AAPL,MSFT"
    )
    mssql_server: str = os.getenv("MSSQL_SERVER", "localhost").strip()
    mssql_database: str = os.getenv(
        "MSSQL_DATABASE", "enterprise_finance"
    ).strip()
    mssql_user: str = os.getenv("MSSQL_USER", "sa").strip()
    mssql_password: str = os.getenv("MSSQL_PASSWORD", "")
    mssql_driver: str = os.getenv(
        "MSSQL_DRIVER", "ODBC Driver 17 for SQL Server"
    ).strip()
    mssql_trusted_connection: str = (
        os.getenv("MSSQL_TRUSTED_CONNECTION", "yes").strip().lower()
    )
    faiss_index_dir: str = os.getenv(
        "FAISS_INDEX_DIR", "data/faiss_index"
    ).strip()
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    @property
    def live_tickers(self) -> List[str]:
        return _parse_tickers(self.live_tickers_raw)

    @property
    def mssql_uri(self) -> str:
        driver_encoded = quote_plus(self.mssql_driver)
        if self.mssql_trusted_connection in ("yes", "true", "1"):
            return (
                f"mssql+pyodbc://@{self.mssql_server}/{self.mssql_database}"
                f"?driver={driver_encoded}&Trusted_Connection=yes"
                "&TrustServerCertificate=yes"
            )
        user_encoded = quote_plus(self.mssql_user)
        pass_encoded = quote_plus(self.mssql_password)
        return (
            f"mssql+pyodbc://{user_encoded}:{pass_encoded}"
            f"@{self.mssql_server}/{self.mssql_database}"
            f"?driver={driver_encoded}&TrustServerCertificate=yes"
        )


def get_groq_llm(temperature: float = 0.0):
    if not settings.groq_api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to your .env file "
            "before querying."
        )
    from langchain_groq import ChatGroq

    return ChatGroq(
        api_key=SecretStr(settings.groq_api_key),
        model=settings.groq_model_name,
        temperature=temperature,
    )


settings = Settings()
