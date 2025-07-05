# services/chunker.py
import logging
from typing import List
from pkg.rag.knowledge.services.base_service import BaseService # Assuming BaseService provides _run_sync

logger = logging.getLogger(__name__)

class Chunker(BaseService):
    """
    A class for splitting long texts into smaller, overlapping chunks.
    """
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        super().__init__() # Initialize BaseService
        self.logger = logging.getLogger(self.__class__.__name__)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        if self.chunk_overlap >= self.chunk_size:
            self.logger.warning("Chunk overlap is greater than or equal to chunk size. This may lead to empty or malformed chunks.")

    def _split_text_sync(self, text: str) -> List[str]:
        """
        Synchronously splits a long text into chunks with specified overlap.
        This is a CPU-bound operation, intended to be run in a separate thread.
        """
        if not text:
            return []

        # Simple whitespace-based splitting for demonstration
        # For more advanced chunking, consider libraries like LangChain's text splitters
        words = text.split()
        chunks = []
        current_chunk = []
        
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) > self.chunk_size:
                chunks.append(" ".join(current_chunk[:self.chunk_size]))
                current_chunk = current_chunk[self.chunk_size - self.chunk_overlap:]
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        # A more robust chunking strategy (e.g., using recursive character text splitter)
        # from langchain.text_splitter import RecursiveCharacterTextSplitter
        # text_splitter = RecursiveCharacterTextSplitter(
        #     chunk_size=self.chunk_size,
        #     chunk_overlap=self.chunk_overlap,
        #     length_function=len,
        #     is_separator_regex=False,
        # )
        # return text_splitter.split_text(text)
        
        return [chunk for chunk in chunks if chunk.strip()] # Filter out empty chunks

    async def chunk(self, text: str) -> List[str]:
        """
        Asynchronously chunks a given text into smaller pieces.
        """
        self.logger.info(f"Chunking text (length: {len(text)})...")
        # Run the synchronous splitting logic in a separate thread
        chunks = await self._run_sync(self._split_text_sync, text)
        self.logger.info(f"Text chunked into {len(chunks)} pieces.")
        return chunks