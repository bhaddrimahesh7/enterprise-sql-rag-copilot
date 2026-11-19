import pandas as pd
import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Live SQL & Financial Document RAG Copilot",
    layout="wide",
)

st.title("Live SQL & Financial Document RAG Copilot")
st.caption(
    "Live Market Sync -> MySQL (sqlglot Read-Only Guard) "
    "+ FAISS Document RAG"
)

with st.sidebar:
    st.header("1. Live Market Data Sync")
    custom_tickers = st.text_input(
        "Tickers (comma-separated)",
        value="RELIANCE.NS,TCS.NS,INFY.NS,AAPL,MSFT",
    )
    if st.button(
        "Sync Live Market Data", type="primary", use_container_width=True
    ):
        with st.spinner("Fetching live snapshots into MySQL..."):
            try:
                ticker_list = [
                    t.strip() for t in custom_tickers.split(",") if t.strip()
                ]
                resp = requests.post(
                    f"{API_URL}/sync-live",
                    json={"tickers": ticker_list},
                    timeout=90,
                )
                if resp.ok:
                    info = resp.json()
                    st.success(
                        f"Synced {info['synced_count']} tickers at "
                        f"{info['synced_at_utc']} UTC"
                    )
                    if info.get("failed_tickers"):
                        st.warning(
                            "Skipped tickers: "
                            + ", ".join(info["failed_tickers"])
                        )
                else:
                    st.error(f"Sync failed: {resp.text}")
            except requests.RequestException as exc:
                st.error(f"API error: {exc}")

    st.divider()
    st.header("2. Ingest Financial PDF")
    uploaded_pdf = st.file_uploader("Upload PDF Report", type=["pdf"])
    if uploaded_pdf is not None and st.button(
        "Index PDF", use_container_width=True
    ):
        with st.spinner("Indexing PDF into FAISS..."):
            try:
                files = {
                    "file": (
                        uploaded_pdf.name,
                        uploaded_pdf.getvalue(),
                        "application/pdf",
                    )
                }
                resp = requests.post(
                    f"{API_URL}/ingest-pdf", files=files, timeout=120
                )
                if resp.ok:
                    info = resp.json()
                    st.success(
                        f"Indexed {info['chunks_indexed']} chunks "
                        f"from {info['filename']}"
                    )
                else:
                    st.error(f"Upload failed: {resp.text}")
            except requests.RequestException as exc:
                st.error(f"API error: {exc}")

question = st.text_input(
    "Ask a question across live MySQL market rows and indexed PDF reports",
    placeholder="E.g., Which synced stock has the highest day_change_pct?",
)

if st.button("Run Copilot Query") and question.strip():
    with st.spinner("Routing and answering..."):
        try:
            resp = requests.post(
                f"{API_URL}/ask",
                json={"question": question.strip(), "top_k": 4},
                timeout=60,
            )
        except requests.RequestException as exc:
            st.error(f"Could not reach FastAPI: {exc}")
            st.stop()

    if not resp.ok:
        st.error(f"Error ({resp.status_code}): {resp.text}")
        st.stop()

    data = resp.json()
    st.info(f"Route Used: **{data['route']}**")
    st.subheader("Answer")
    st.write(data["answer"])

    col_sql, col_rag = st.columns(2)
    with col_sql:
        st.subheader("Executed SQL & Live Table Rows")
        if data.get("executed_sql"):
            st.code(data["executed_sql"], language="sql")
            rows = data.get("sql_rows") or []
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True)
            else:
                st.caption("No rows returned.")
        else:
            st.caption("SQL not triggered for this prompt.")

    with col_rag:
        st.subheader("PDF Vector Citations")
        citations = data.get("citations") or []
        if citations:
            for idx, item in enumerate(citations, start=1):
                with st.expander(
                    f"{idx}. {item['source']} (Page {item['page']})"
                ):
                    st.write(item["content"])
        else:
            st.caption("No PDF citations retrieved for this prompt.")
