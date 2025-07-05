
import numpy as np
import logging
from chromadb import PersistentClient
import os

logger = logging.getLogger(__name__)

class ChromaIndexManager:
    def __init__(self, collection_name: str = "default_collection"):
        self.logger = logging.getLogger(self.__class__.__name__)
        chroma_data_path = os.path.abspath(os.path.join(__file__, "../../../../../../data/chroma"))
        os.makedirs(chroma_data_path, exist_ok=True)
        self.client = PersistentClient(path=chroma_data_path)
        self._collection_name = collection_name
        self._collection = None

        self.logger.info(f"ChromaIndexManager initialized. Collection name: {self._collection_name}")

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(name=self._collection_name)
            self.logger.info(f"Chroma collection '{self._collection_name}' accessed/created.")
        return self._collection

    def add_embeddings_sync(self, file_ids: list[int], chunk_ids: list[int], embeddings: np.ndarray, documents: list[str]):
        if embeddings.shape[0] != len(chunk_ids) or embeddings.shape[0] != len(file_ids) or embeddings.shape[0] != len(documents):
            raise ValueError("Embedding, file_id, chunk_id, and document count mismatch.")

        chroma_ids = [f"{file_id}_{chunk_id}" for file_id, chunk_id in zip(file_ids, chunk_ids)]
        metadatas = [{"file_id": fid, "chunk_id": cid} for fid, cid in zip(file_ids, chunk_ids)]

        self.logger.debug(f"Adding {len(embeddings)} embeddings to Chroma collection '{self._collection_name}'.")
        self.collection.add(
            embeddings=embeddings.tolist(),
            ids=chroma_ids,
            metadatas=metadatas,
            documents=documents
        )
        self.logger.info(f"Added {len(embeddings)} embeddings to Chroma collection '{self._collection_name}'.")

    def search_sync(self, query_embedding: np.ndarray, k: int = 5):
        """
        Searches the Chroma collection for the top-k nearest neighbors.
        Args:
            query_embedding: A numpy array of the query embedding.
            k: The number of results to return.
        Returns:
            A dictionary containing query results from Chroma.
        """
        self.logger.debug(f"Searching Chroma collection '{self._collection_name}' with k={k}.")
        results = self.collection.query(
            query_embeddings=query_embedding.tolist(),
            n_results=k,
            # REMOVE 'ids' from the include list. It's returned by default.
            include=["metadatas", "distances", "documents"]
        )
        self.logger.debug(f"Chroma search returned {len(results.get('ids', [[]])[0])} results.")
        return results

    def delete_by_file_id_sync(self, file_id: int):
        self.logger.info(f"Deleting embeddings for file_id: {file_id} from Chroma collection '{self._collection_name}'.")
        self.collection.delete(where={"file_id": file_id})
        self.logger.info(f"Deleted embeddings for file_id: {file_id} from Chroma.")