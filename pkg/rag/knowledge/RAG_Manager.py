# RAG_Manager class (main class, adjust imports as needed)
from __future__ import annotations  # For type hinting in Python 3.7+
import logging
import os
import asyncio
from pkg.rag.knowledge.services.parser import FileParser
from pkg.rag.knowledge.services.chunker import Chunker
from pkg.rag.knowledge.services.embedder import Embedder
from pkg.rag.knowledge.services.retriever import Retriever
from pkg.rag.knowledge.services.database import create_db_and_tables, SessionLocal, KnowledgeBase, File, Chunk # Ensure Chunk is imported if you need to manipulate it directly
from pkg.rag.knowledge.services.embedding_models import EmbeddingModelFactory
from pkg.rag.knowledge.services.chroma_manager import ChromaIndexManager
from pkg.core import app  # Adjust the import path as needed


class RAG_Manager:

    ap: app.Application

    def __init__(self, ap: app.Application,logger: logging.Logger = None):
        self.ap = ap
        self.logger = logger or logging.getLogger(__name__)
        self.embedding_model_type = None
        self.embedding_model_name = None
        self.chroma_manager = None
        self.parser = None
        self.chunker = None
        self.embedder = None
        self.retriever = None

    async def initialize_rag_system(self):
        await asyncio.to_thread(create_db_and_tables)

    async def create_specific_model(self, embedding_model_type: str,
                 embedding_model_name: str):
        self.embedding_model_type = embedding_model_type
        self.embedding_model_name = embedding_model_name

        try:
            model = EmbeddingModelFactory.create_model(
                model_type=self.embedding_model_type,
                model_name_key=self.embedding_model_name
            )
            self.logger.info(f"Configured embedding model '{self.embedding_model_name}' has dimension: {model.embedding_dimension}")
        except Exception as e:
            self.logger.critical(f"Failed to get dimension for configured embedding model '{self.embedding_model_name}': {e}")
            raise RuntimeError("Failed to initialize RAG_Manager due to embedding model issues.")

        self.chroma_manager = ChromaIndexManager(collection_name=f"rag_collection_{self.embedding_model_name.replace('-', '_')}")

        self.parser = FileParser()
        self.chunker = Chunker()
        # Pass chroma_manager to Embedder and Retriever
        self.embedder = Embedder(
            model_type=self.embedding_model_type,
            model_name_key=self.embedding_model_name,
            chroma_manager=self.chroma_manager # Inject dependency
        )
        self.retriever = Retriever(
            model_type=self.embedding_model_type,
            model_name_key=self.embedding_model_name,
            chroma_manager=self.chroma_manager # Inject dependency
        )


    async def create_knowledge_base(self, kb_name: str, kb_description: str, embedding_model: str = "", top_k: int = 5):
        """
        Creates a new knowledge base with the given name and description.
        If a knowledge base with the same name already exists, it returns that one.
        """
        try:
            def _get_kb_sync(name):
                session = SessionLocal()
                try:
                    return session.query(KnowledgeBase).filter_by(name=name).first()
                finally:
                    session.close()

            kb = await asyncio.to_thread(_get_kb_sync, kb_name)

            if not kb:
                def _add_kb_sync():
                    session = SessionLocal()
                    try:
                        new_kb = KnowledgeBase(name=kb_name, description=kb_description, embedding_model=embedding_model, top_k=top_k)
                        session.add(new_kb)
                        session.commit()
                        session.refresh(new_kb)
                        return new_kb
                    finally:
                        session.close()
                kb = await asyncio.to_thread(_add_kb_sync)
        except Exception as e:
            self.logger.error(f"Error creating knowledge base '{kb_name}': {str(e)}", exc_info=True)
            raise
        except Exception as e:
            self.logger.error(f"Error creating knowledge base '{kb_name}': {str(e)}", exc_info=True)
            raise

    async def get_all_knowledge_bases(self):
        """
        Retrieves all knowledge bases from the database.
        """
        try:
            def _get_all_kbs_sync():
                session = SessionLocal()
                try:
                    return session.query(KnowledgeBase).all()
                finally:
                    session.close()

            kbs = await asyncio.to_thread(_get_all_kbs_sync)
            return kbs
        except Exception as e:
            self.logger.error(f"Error retrieving knowledge bases: {str(e)}", exc_info=True)
            return []
        
    async def get_knowledge_base_by_id(self, kb_id: int):
        """
        Retrieves a knowledge base by its ID.
        """
        try:
            def _get_kb_sync(kb_id):
                session = SessionLocal()
                try:
                    return session.query(KnowledgeBase).filter_by(id=kb_id).first()
                finally:
                    session.close()

            kb = await asyncio.to_thread(_get_kb_sync, kb_id)
            return kb
        except Exception as e:
            self.logger.error(f"Error retrieving knowledge base with ID {kb_id}: {str(e)}", exc_info=True)
            return None
        
    async def get_files_by_knowledge_base(self, kb_id: int):
        try:
            def _get_files_sync(kb_id):
                session = SessionLocal()
                try:
                    return session.query(File).filter_by(kb_id=kb_id).all()
                finally:
                    session.close()

            files = await asyncio.to_thread(_get_files_sync, kb_id)
            return files
        except Exception as e:
            self.logger.error(f"Error retrieving files for knowledge base ID {kb_id}: {str(e)}", exc_info=True)
            return []


    async def store_data(self, file_path: str, kb_name: str, file_type: str, kb_description: str = "Default knowledge base"):
        self.logger.info(f"Starting data storage process for file: {file_path}")
        try:
            def _get_kb_sync(name):
                session = SessionLocal()
                try:
                    return session.query(KnowledgeBase).filter_by(name=name).first()
                finally:
                    session.close()

            kb = await asyncio.to_thread(_get_kb_sync, kb_name)

            if not kb:
                self.logger.info(f"Knowledge Base '{kb_name}' not found. Creating a new one.")
                def _add_kb_sync():
                    session = SessionLocal()
                    try:
                        new_kb = KnowledgeBase(name=kb_name, description=kb_description)
                        session.add(new_kb)
                        session.commit()
                        session.refresh(new_kb)
                        return new_kb
                    finally:
                        session.close()
                kb = await asyncio.to_thread(_add_kb_sync)
                self.logger.info(f"Created Knowledge Base: {kb.name} (ID: {kb.id})")

            def _add_file_sync(kb_id, file_name, path, file_type):
                session = SessionLocal()
                try:
                    file = File(kb_id=kb_id, file_name=file_name, path=path, file_type=file_type)
                    session.add(file)
                    session.commit()
                    session.refresh(file)
                    return file
                finally:
                    session.close()

            file_obj = await asyncio.to_thread(_add_file_sync, kb.id, os.path.basename(file_path), file_path, file_type)
            self.logger.info(f"Added file entry: {file_obj.file_name} (ID: {file_obj.id})")

            text = await self.parser.parse(file_path)
            if not text:
                self.logger.warning(f"File {file_path} parsed to empty content. Skipping chunking and embedding.")
                # You might want to delete the file_obj from the DB here if it's empty.
                session = SessionLocal()
                try:
                    session.delete(file_obj)
                    session.commit()
                except Exception as del_e:
                    self.logger.error(f"Failed to delete empty file_obj {file_obj.id}: {del_e}")
                finally:
                    session.close()
                return

            chunks_texts = await self.chunker.chunk(text)
            self.logger.info(f"Chunked into {len(chunks_texts)} pieces.")

            # embed_and_store now handles both DB chunk saving and Chroma embedding
            await self.embedder.embed_and_store(file_id=file_obj.id, chunks=chunks_texts)

            self.logger.info(f"Data storage process completed for file: {file_path}")

        except Exception as e:
            self.logger.error(f"Error in store_data for file {file_path}: {str(e)}", exc_info=True)
            # Consider cleaning up partially stored data if an error occurs.
            return

    async def retrieve_data(self, query: str):
        self.logger.info(f"Starting data retrieval process for query: '{query}'")
        try:
            retrieved_chunks = await self.retriever.retrieve(query)
            self.logger.info(f"Successfully retrieved {len(retrieved_chunks)} chunks for query.")
            return retrieved_chunks
        except Exception as e:
            self.logger.error(f"Error in retrieve_data for query '{query}': {str(e)}", exc_info=True)
            return []

    async def delete_data_by_file_id(self, file_id: int):
        """
        Deletes data associated with a specific file_id from both the relational DB and Chroma.
        """
        self.logger.info(f"Starting data deletion process for file_id: {file_id}")
        session = SessionLocal()
        try:
            # 1. Delete from Chroma
            await asyncio.to_thread(self.chroma_manager.delete_by_file_id_sync, file_id)

            # 2. Delete chunks from relational DB
            chunks_to_delete = session.query(Chunk).filter_by(file_id=file_id).all()
            for chunk in chunks_to_delete:
                session.delete(chunk)
            self.logger.info(f"Deleted {len(chunks_to_delete)} chunks from relational DB for file_id: {file_id}.")

            # 3. Delete file entry from relational DB
            file_to_delete = session.query(File).filter_by(id=file_id).first()
            if file_to_delete:
                session.delete(file_to_delete)
                self.logger.info(f"Deleted file entry {file_id} from relational DB.")
            else:
                self.logger.warning(f"File entry {file_id} not found in relational DB.")

            session.commit()
            self.logger.info(f"Data deletion completed for file_id: {file_id}.")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting data for file_id {file_id}: {str(e)}", exc_info=True)
        finally:
            session.close()

    async def delete_kb_by_id(self, kb_id: int):
        """
        Deletes a knowledge base and all associated files and chunks.
        """
        self.logger.info(f"Starting deletion of knowledge base with ID: {kb_id}")
        session = SessionLocal()
        try:
            # 1. Get the knowledge base
            kb = session.query(KnowledgeBase).filter_by(id=kb_id).first()
            if not kb:
                self.logger.warning(f"Knowledge Base with ID {kb_id} not found.")
                return

            # 2. Delete all files associated with this knowledge base
            files_to_delete = session.query(File).filter_by(kb_id=kb.id).all()
            for file in files_to_delete:
                await self.delete_data_by_file_id(file.id)

            # 3. Delete the knowledge base itself
            session.delete(kb)
            session.commit()
            self.logger.info(f"Successfully deleted knowledge base with ID: {kb_id}")
        except Exception as e:
            session.rollback()
            self.logger.error(f"Error deleting knowledge base with ID {kb_id}: {str(e)}", exc_info=True)
        finally:
            session.close()
