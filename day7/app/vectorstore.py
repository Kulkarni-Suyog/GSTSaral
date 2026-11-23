"""Persistent ChromaDB vector store for GSTSaral document chunks."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from app.chunking import DocumentChunk, build_all_chunks
from app.embed import LocalEmbeddingFunction

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CHROMA_DIR = ROOT_DIR / "data" / "chroma_db"
COLLECTION_NAME = "gstsaral_chunks"


class GSTSaralVectorStore:
    """Manages indexing and querying GSTSaral chunks in a persistent Chroma collection."""

    def __init__(
        self,
        persist_dir: Path = DEFAULT_CHROMA_DIR,
        collection_name: str = COLLECTION_NAME,
        embedder: Optional[LocalEmbeddingFunction] = None,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedder = embedder or LocalEmbeddingFunction()

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index_chunks(self, chunks: Optional[List[DocumentChunk]] = None, reset: bool = True) -> int:
        """Index all chunks (with source, page, title metadata) into ChromaDB."""
        items = chunks if chunks is not None else build_all_chunks()
        if reset:
            try:
                self.client.delete_collection(self.collection_name)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )

        if not items:
            return 0

        ids = [c.chunk_id for c in items]
        documents = [c.text for c in items]
        metadatas = [
            {
                "title": c.title,
                "source": c.source,
                "page": int(c.page),
                "source_url": c.source_url,
            }
            for c in items
        ]
        embeddings = self.embedder.embed_texts(documents)

        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        return len(items)

    def ensure_indexed(self) -> int:
        """Index chunks automatically if the persistent collection is currently empty."""
        existing = self.collection.count()
        if existing == 0:
            return self.index_chunks(reset=False)
        return existing

    def semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Query the persistent Chroma collection and return ranked chunks with metadata."""
        cleaned = (query or "").strip()
        if not cleaned:
            return []

        total = self.ensure_indexed()
        if total == 0:
            return []

        q_emb = self.embedder.embed_texts([cleaned])
        n_results = min(top_k, total)
        raw = self.collection.query(
            query_embeddings=q_emb,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        hits: List[Dict[str, Any]] = []
        ids = raw.get("ids", [[]])[0]
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        dists = raw.get("distances", [[]])[0]

        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            # Chroma cosine distance = 1 - cosine_similarity
            similarity = round(max(0.0, 1.0 - float(dist)), 4)
            hits.append(
                {
                    "chunk_id": cid,
                    "score": similarity,
                    "title": meta.get("title", ""),
                    "source": meta.get("source", ""),
                    "page": meta.get("page", 1),
                    "source_url": meta.get("source_url", ""),
                    "text": doc,
                }
            )
        return hits


if __name__ == "__main__":
    store = GSTSaralVectorStore()
    count = store.index_chunks(reset=True)
    print(f"Indexed {count} chunks into persistent Chroma collection '{COLLECTION_NAME}' at {DEFAULT_CHROMA_DIR}")
    sample = store.semantic_search("What is the GST rate on milk and paneer?", top_k=3)
    for hit in sample:
        print(hit)
