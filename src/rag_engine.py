import os
from typing import Any, Dict, List
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import settings


class FinancialDocumentRAG:
    def __init__(self) -> None:
        self._embeddings = None
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=120,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        if self._embeddings is None:
            self._embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model
            )
        return self._embeddings

    def _has_index(self) -> bool:
        index_faiss = os.path.join(settings.faiss_index_dir, "index.faiss")
        index_pkl = os.path.join(settings.faiss_index_dir, "index.pkl")
        return os.path.isfile(index_faiss) and os.path.isfile(index_pkl)

    def ingest_pdf(self, pdf_path: str) -> int:
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        chunks = [
            doc
            for doc in self.splitter.split_documents(pages)
            if doc.page_content and doc.page_content.strip()
        ]
        if not chunks:
            return 0

        if self._has_index():
            store = FAISS.load_local(
                settings.faiss_index_dir,
                self.embeddings,
                allow_dangerous_deserialization=True,
            )
            store.add_documents(chunks)
        else:
            store = FAISS.from_documents(chunks, self.embeddings)

        os.makedirs(settings.faiss_index_dir, exist_ok=True)
        store.save_local(settings.faiss_index_dir)
        return len(chunks)

    def retrieve(self, question: str, top_k: int = 4) -> List[Dict[str, Any]]:
        if not self._has_index():
            return []

        store = FAISS.load_local(
            settings.faiss_index_dir,
            self.embeddings,
            allow_dangerous_deserialization=True,
        )
        docs = store.similarity_search(question, k=top_k)
        return [
            {
                "source": os.path.basename(
                    str(doc.metadata.get("source", "report.pdf"))
                ),
                "page": int(doc.metadata.get("page", 0)) + 1,
                "content": doc.page_content.strip(),
            }
            for doc in docs
        ]
