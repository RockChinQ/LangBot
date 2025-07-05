# services/embedder.py
import asyncio
import logging
import numpy as np
from typing import List
from sqlalchemy.orm import Session
from pkg.rag.knowledge.services.base_service import BaseService
from pkg.rag.knowledge.services.database import Chunk, SessionLocal
from pkg.rag.knowledge.services.embedding_models import BaseEmbeddingModel, EmbeddingModelFactory
from pkg.rag.knowledge.services.chroma_manager import ChromaIndexManager # Import the manager

logger = logging.getLogger(__name__)

class Embedder(BaseService):
    def __init__(self, model_type: str, model_name_key: str, chroma_manager: ChromaIndexManager):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.model_type = model_type
        self.model_name_key = model_name_key
        self.chroma_manager = chroma_manager # Dependency Injection

        self.embedding_model: BaseEmbeddingModel = self._load_embedding_model()

    def _load_embedding_model(self) -> BaseEmbeddingModel:
        self.logger.info(f"Loading embedding model: type={self.model_type}, name_key={self.model_name_key}...")
        try:
            model = EmbeddingModelFactory.create_model(self.model_type, self.model_name_key)
            self.logger.info(f"Embedding model '{self.model_name_key}' loaded. Output dimension: {model.embedding_dimension}")
            return model
        except Exception as e:
            self.logger.error(f"Failed to load embedding model '{self.model_name_key}': {e}")
            raise

    def _db_save_chunks_sync(self, session: Session, file_id: int, chunks_texts: List[str]):
        """
        Saves chunks to the relational database and returns the created Chunk objects.
        This function assumes it's called within a context where the session
        will be committed/rolled back and closed by the caller.
        """
        self.logger.debug(f"Saving {len(chunks_texts)} chunks for file_id {file_id} to DB (sync).")
        chunk_objects = []
        for text in chunks_texts:
            chunk = Chunk(file_id=file_id, text=text)
            session.add(chunk)
            chunk_objects.append(chunk)
        session.flush() # This populates the .id attribute for each new chunk object
        self.logger.debug(f"Successfully added {len(chunk_objects)} chunk entries to DB.")
        return chunk_objects

    async def embed_and_store(self, file_id: int, chunks: List[str]):
        if not self.embedding_model:
            raise RuntimeError("Embedding model not loaded. Please check Embedder initialization.")

        self.logger.info(f"Embedding {len(chunks)} chunks for file_id: {file_id} using {self.model_name_key}...")

        session = SessionLocal() # Start a session that will live for the whole operation
        chunk_objects = []
        try:
            # 1. Save chunks to the relational database first to get their IDs
            #    We call _db_save_chunks_sync directly without _run_sync's session management
            #    because we manage the session here across multiple async calls.
            chunk_objects = await asyncio.to_thread(self._db_save_chunks_sync, session, file_id, chunks)
            session.commit() # Commit chunks to make their IDs permanent and accessible

            if not chunk_objects:
                self.logger.warning(f"No chunk objects created for file_id {file_id}. Skipping embedding and Chroma storage.")
                return []

            # 2. Generate embeddings
            embeddings: List[List[float]] = await self.embedding_model.embed_documents(chunks)
            embeddings_np = np.array(embeddings, dtype=np.float32)

            if embeddings_np.shape[1] != self.embedding_model.embedding_dimension:
                self.logger.error(f"Mismatch in embedding dimension: Model returned {embeddings_np.shape[1]}, expected {self.embedding_model.embedding_dimension}. Aborting storage.")
                raise ValueError("Embedding dimension mismatch during embedding process.")

            self.logger.info("Saving embeddings to Chroma...")
            chunk_ids = [c.id for c in chunk_objects] # Now safe to access .id because session is still open and committed
            file_ids_for_chroma = [file_id] * len(chunk_ids)

            await self._run_sync( # Use _run_sync for the Chroma operation, as it's a sync call
                self.chroma_manager.add_embeddings_sync,
                file_ids_for_chroma, chunk_ids, embeddings_np, chunks # Pass original chunks texts for documents
            )
            self.logger.info(f"Successfully saved {len(chunk_objects)} embeddings to Chroma.")
            return chunk_objects

        except Exception as e:
            session.rollback() # Rollback on any error
            self.logger.error(f"Failed to process and store data for file_id {file_id}: {e}", exc_info=True)
            raise # Re-raise the exception to propagate it
        finally:
            session.close() # Ensure the session is always closed