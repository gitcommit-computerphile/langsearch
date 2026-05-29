from pathlib import Path
from typing import Optional

from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DATA_DIR = Path(__file__).parent.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma_db"
COLLECTION_NAME = "knowledge_base"

_embeddings: Optional[HuggingFaceEmbeddings] = None
_vectorstore: Optional[Chroma] = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def get_vectorstore() -> Chroma:
    global _vectorstore
    if _vectorstore is None:
        DATA_DIR.mkdir(exist_ok=True)
        _vectorstore = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=_get_embeddings(),
            persist_directory=str(CHROMA_DIR),
        )
    return _vectorstore


def get_retriever(k: int = 4):
    return get_vectorstore().as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


def ingest_file(file_path: str) -> int:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        loader = PyPDFLoader(file_path)
    else:
        loader = TextLoader(file_path, encoding="utf-8")

    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    chunks = splitter.split_documents(docs)

    store = get_vectorstore()
    store.add_documents(chunks)
    return len(chunks)


def ingest_text(text: str, metadata: Optional[dict] = None) -> int:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
    docs = [Document(page_content=text, metadata=metadata or {})]
    chunks = splitter.split_documents(docs)
    get_vectorstore().add_documents(chunks)
    return len(chunks)


def collection_count() -> int:
    return get_vectorstore()._collection.count()
