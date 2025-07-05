# services/retriever.py
import asyncio
import logging
import numpy as np # Make sure numpy is imported
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from pkg.rag.knowledge.services.base_service import BaseService
from pkg.rag.knowledge.services.database import Chunk, SessionLocal
from pkg.rag.knowledge.services.embedding_models import BaseEmbeddingModel, EmbeddingModelFactory
from pkg.rag.knowledge.services.chroma_manager import ChromaIndexManager

logger = logging.getLogger(__name__)

class Retriever(BaseService):
    def __init__(self, model_type: str, model_name_key: str, chroma_manager: ChromaIndexManager):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model_type = model_type
        self.model_name_key = model_name_key
        self.chroma_manager = chroma_manager

        self.embedding_model: BaseEmbeddingModel = self._load_embedding_model()

    def _load_embedding_model(self) -> BaseEmbeddingModel:
        self.logger.info(f"Loading retriever embedding model: type={self.model_type}, name_key={self.model_name_key}...")
        try:
            model = EmbeddingModelFactory.create_model(self.model_type, self.model_name_key)
            self.logger.info(f"Retriever embedding model '{self.model_name_key}' loaded. Output dimension: {model.embedding_dimension}")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load retriever embedding model '{self.model_name_key}': {e}")
            raise

    async def retrieve(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if not self.embedding_model:
            raise RuntimeError("Retriever embedding model not loaded. Please check Retriever initialization.")

        self.logger.info(f"Retrieving for query: '{query}' with k={k} using {self.model_name_key}")

        query_embedding: List[float] = await self.embedding_model.embed_query(query)
        query_embedding_np = np.array([query_embedding], dtype=np.float32)

        chroma_results = await self._run_sync(
            self.chroma_manager.search_sync,
            query_embedding_np, k
        )

        # 'ids' is always returned by ChromaDB, even if not explicitly in 'include'
        matched_chroma_ids = chroma_results.get("ids", [[]])[0]
        distances = chroma_results.get("distances", [[]])[0]
        chroma_metadatas = chroma_results.get("metadatas", [[]])[0]
        chroma_documents = chroma_results.get("documents", [[]])[0]

        if not matched_chroma_ids:
            self.logger.info("No relevant chunks found in Chroma.")
            return []

        db_chunk_ids = []
        for metadata in chroma_metadatas:
            if "chunk_id" in metadata:
                db_chunk_ids.append(metadata["chunk_id"])
            else:
                self.logger.warning(f"Metadata missing 'chunk_id': {metadata}. Skipping this entry.")

        if not db_chunk_ids:
            self.logger.warning("No valid chunk_ids extracted from Chroma results metadata.")
            return []

        self.logger.info(f"Fetching {len(db_chunk_ids)} chunk details from relational database...")
        chunks_from_db = await self._run_sync(
            lambda cids: self._db_get_chunks_sync(SessionLocal(), cids), # Ensure SessionLocal is passed correctly for _db_get_chunks_sync
            db_chunk_ids
        )

        chunk_map = {chunk.id: chunk for chunk in chunks_from_db}
        results_list: List[Dict[str, Any]] = []

        for i, chroma_id in enumerate(matched_chroma_ids):
            try:
                # Ensure original_chunk_id is int for DB lookup
                original_chunk_id = int(chroma_id.split('_')[-1])
            except (ValueError, IndexError):
                self.logger.warning(f"Could not parse chunk_id from Chroma ID: {chroma_id}. Skipping.")
                continue

            chunk_text_from_chroma = chroma_documents[i]
            distance = float(distances[i])
            file_id_from_chroma = chroma_metadatas[i].get("file_id")

            chunk_from_db = chunk_map.get(original_chunk_id)

            results_list.append({
                "chunk_id": original_chunk_id,
                "text": chunk_from_db.text if chunk_from_db else chunk_text_from_chroma,
                "distance": distance,
                "file_id": file_id_from_chroma
            })

        self.logger.info(f"Retrieved {len(results_list)} chunks.")
        return results_list

    def _db_get_chunks_sync(self, session: Session, chunk_ids: List[int]) -> List[Chunk]:
        self.logger.debug(f"Fetching {len(chunk_ids)} chunk details from database (sync).")
        chunks = session.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
        session.close()
        return chunks