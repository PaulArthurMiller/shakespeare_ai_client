import chromadb
from chromadb.config import Settings
import time
from typing import cast, Mapping, Union
from modules.utils.logger import CustomLogger

class VectorStore:
    def __init__(self, path="embeddings/chromadb_vectors", collection_name="shakespeare_chunks", logger=None):
        self.logger = logger or CustomLogger("VectorStore")
        self.logger.info(f"Initializing ChromaDB at {path}")
        self.client = chromadb.PersistentClient(path=path, settings=Settings(allow_reset=True))
        self.collection = self.client.get_or_create_collection(name=collection_name)
        self.logger.info(f"Using collection: {collection_name}")

    def add_documents(self, chunks):
        BATCH_LIMIT = 1000
        total = len(chunks)
        self.logger.info(f"Preparing to insert {total} chunks in batches of {BATCH_LIMIT}")

        for i in range(0, total, BATCH_LIMIT):
            batch = chunks[i:i+BATCH_LIMIT]
            documents = [c["text"] for c in batch]
            ids = [c["chunk_id"] for c in batch]
            embeddings = [c["embedding"] for c in batch]

            metadatas = []
            for chunk in batch:
                clean_meta = {
                    k: v for k, v in chunk.items()
                    if k not in ("text", "embedding", "chunk_id")
                    and isinstance(v, (str, int, float, bool))
                }
                metadatas.append(clean_meta)

            self.logger.debug(f"Adding batch {i // BATCH_LIMIT + 1}: {len(batch)} documents")
            try:
                self.collection.add(
                    documents=documents,
                    embeddings=embeddings,
                    ids=ids,
                    metadatas=metadatas,
                )
                time.sleep(0.25)  # 🔧 Key: Let Chroma's segment manager breathe
            except Exception as e:
                self.logger.error(f"❌ Failed to insert batch {i // BATCH_LIMIT + 1}: {e}")
                raise

        self.logger.info("✅ All documents successfully added to Chroma")

    def query(self, query_text, embedding_function, n_results=5):
        self.logger.debug(f"Querying for: {query_text}")
        query_embedding = embedding_function([query_text])[0]
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )
