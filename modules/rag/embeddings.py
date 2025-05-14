import os
import json
import openai
from dotenv import load_dotenv
from typing import List, Dict, Any
from modules.utils.logger import CustomLogger

load_dotenv()

class EmbeddingGenerator:
    def __init__(self, model_name='text-embedding-3-large', logger=None):
        self.model_name = model_name
        self.logger = logger or CustomLogger("EmbeddingGenerator")
        self.logger.info(f"Using embedding model: {self.model_name}")

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        self.logger.debug(f"Embedding {len(texts)} texts")

        MAX_TOKENS = 600_000
        BATCH_SIZE_LIMIT = 1500  # fallback: max number of items per batch

        def estimate_tokens(text: str) -> int:
            return int(len(text.split()) * 1.33)

        batches = []
        current_batch = []
        current_tokens = 0

        for text in texts:
            tokens = estimate_tokens(text)
            if (current_tokens + tokens > MAX_TOKENS) or (len(current_batch) >= BATCH_SIZE_LIMIT):
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            current_batch.append(text)
            current_tokens += tokens

        if current_batch:
            batches.append(current_batch)

        self.logger.info(f"Splitting into {len(batches)} batches for embedding")

        all_embeddings = []
        for idx, batch in enumerate(batches):
            self.logger.debug(f"Sending batch {idx + 1}/{len(batches)} with {len(batch)} texts")
            try:
                response = openai.embeddings.create(
                    input=batch,
                    model=self.model_name
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                self.logger.error(f"Error embedding batch {idx + 1}: {e}")
                raise

        return all_embeddings

    def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        texts = [chunk['text'] for chunk in chunks]
        embeddings = self.embed_texts(texts)
        for chunk, vector in zip(chunks, embeddings):
            chunk['embedding'] = vector
        self.logger.info(f"Embedded {len(chunks)} chunks with vectors")
        return chunks

    def save_embedded_chunks(self, chunks: List[Dict[str, Any]], output_path: str):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2)
        self.logger.info(f"Saved embedded chunks to {output_path}")
