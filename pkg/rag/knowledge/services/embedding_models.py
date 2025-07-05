# services/embedding_models.py

import os
from typing import Dict, Any, List, Type, Optional
import logging
import aiohttp # Import aiohttp for asynchronous requests
import asyncio
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Base class for all embedding models
class BaseEmbeddingModel:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._embedding_dimension = None

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronously embeds a list of texts."""
        raise NotImplementedError

    async def embed_query(self, text: str) -> List[float]:
        """Asynchronously embeds a single query text."""
        raise NotImplementedError

    @property
    def embedding_dimension(self) -> int:
        """Returns the embedding dimension of the model."""
        if self._embedding_dimension is None:
            raise NotImplementedError("Embedding dimension not set for this model.")
        return self._embedding_dimension
    
class EmbeddingModelFactory:
    @staticmethod
    def create_model(model_type: str, model_name_key: str) -> BaseEmbeddingModel:
        """
        Factory method to create an embedding model instance.
        Currently only supports 'third_party_api' types.
        """
        if model_name_key not in EMBEDDING_MODEL_CONFIGS:
            raise ValueError(f"Embedding model configuration '{model_name_key}' not found in EMBEDDING_MODEL_CONFIGS.")
        
        config = EMBEDDING_MODEL_CONFIGS[model_name_key]
        
        if config['type'] == "third_party_api":
            required_keys = ['api_endpoint', 'headers', 'payload_template', 'embedding_dimension']
            if not all(key in config for key in required_keys):
                raise ValueError(f"Missing configuration keys for third_party_api model '{model_name_key}'. Required: {required_keys}")
            
            # Retrieve model_name from config if it differs from model_name_key
            # Some APIs expect a specific 'model' value in the payload that might be different from the key
            api_model_name = config.get('model_name', model_name_key) 

            return ThirdPartyAPIEmbeddingModel(
                model_name=api_model_name, # Use the model_name from config or the key
                api_endpoint=config['api_endpoint'],
                headers=config['headers'],
                payload_template=config['payload_template'],
                embedding_dimension=config['embedding_dimension']
            )

class SentenceTransformerEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model_name: str):
        super().__init__(model_name)
        try:
            # SentenceTransformer is inherently synchronous, but we'll wrap its calls
            # in async methods. The actual computation will still block the event loop
            # if not run in a separate thread/process, but this keeps the API consistent.
            self.model = SentenceTransformer(model_name)
            self._embedding_dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Initialized SentenceTransformer model '{model_name}' with dimension {self._embedding_dimension}")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model {model_name}: {e}")
            raise

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # For CPU-bound tasks like local model inference, consider running in a thread pool
        # to prevent blocking the event loop for long operations.
        # For simplicity here, we'll call it directly.
        return self.model.encode(texts).tolist()

    async def embed_query(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()


class ThirdPartyAPIEmbeddingModel(BaseEmbeddingModel):
    def __init__(self, model_name: str, api_endpoint: str, headers: Dict[str, str], payload_template: Dict[str, Any], embedding_dimension: int):
        super().__init__(model_name)
        self.api_endpoint = api_endpoint
        self.headers = headers
        self.payload_template = payload_template
        self._embedding_dimension = embedding_dimension
        self.session = None # aiohttp client session will be initialized on first use or in a context manager
        logger.info(f"Initialized ThirdPartyAPIEmbeddingModel '{model_name}' for async calls to {api_endpoint} with dimension {embedding_dimension}")

    async def _get_session(self):
        """Lazily create or return the aiohttp client session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close_session(self):
        """Explicitly close the aiohttp client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.info(f"Closed aiohttp session for model {self.model_name}")

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronously embeds a list of texts using the third-party API."""
        session = await self._get_session()
        embeddings = []
        tasks = []
        for text in texts:
            payload = self.payload_template.copy()
            if 'input' in payload:
                payload['input'] = text
            elif 'texts' in payload:
                payload['texts'] = [text]
            else:
                raise ValueError("Payload template does not contain expected text input key.")

            tasks.append(self._make_api_request(session, payload))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                logger.error(f"Error embedding text '{texts[i][:50]}...': {res}")
                # Depending on your error handling strategy, you might:
                # - Append None or an empty list
                # - Re-raise the exception to stop processing
                # - Log and skip, then continue
                embeddings.append([0.0] * self.embedding_dimension) # Append dummy embedding or handle failure
            else:
                embeddings.append(res)
        
        return embeddings

    async def _make_api_request(self, session: aiohttp.ClientSession, payload: Dict[str, Any]) -> List[float]:
        """Helper to make an asynchronous API request and extract embedding."""
        try:
            async with session.post(self.api_endpoint, headers=self.headers, json=payload) as response:
                response.raise_for_status() # Raise an exception for HTTP errors (4xx, 5xx)
                api_response = await response.json()
                
                # Adjust this based on your API's actual response structure
                if "data" in api_response and len(api_response["data"]) > 0 and "embedding" in api_response["data"][0]:
                    embedding = api_response["data"][0]["embedding"]
                    if len(embedding) != self.embedding_dimension:
                        logger.warning(f"API returned embedding of dimension {len(embedding)}, but expected {self.embedding_dimension} for model {self.model_name}. Adjusting config might be needed.")
                    return embedding
                elif "embeddings" in api_response and isinstance(api_response["embeddings"], list) and api_response["embeddings"]:
                    embedding = api_response["embeddings"][0]
                    if len(embedding) != self.embedding_dimension:
                         logger.warning(f"API returned embedding of dimension {len(embedding)}, but expected {self.embedding_dimension} for model {self.model_name}. Adjusting config might be needed.")
                    return embedding
                else:
                    raise ValueError(f"Unexpected API response structure: {api_response}")

        except aiohttp.ClientError as e:
            raise ConnectionError(f"API request failed: {e}") from e
        except ValueError as e:
            raise ValueError(f"Error processing API response: {e}") from e


    async def embed_query(self, text: str) -> List[float]:
        """Asynchronously embeds a single query text."""
        results = await self.embed_documents([text])
        if results:
            return results[0]
        return [] # Or raise an error if embedding a query must always succeed

# --- Embedding Model Configuration ---
EMBEDDING_MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "MiniLM": { # Example for a local Sentence Transformer model
        "type": "sentence_transformer",
        "model_name": "sentence-transformers/all-MiniLM-L6-v2"
    },
    "bge-m3": { # Example for a third-party API model
        "type": "third_party_api",
        "model_name": "bge-m3",
        "api_endpoint": "https://api.qhaigc.net/v1/embeddings",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('rag_api_key')}"
        },
        "payload_template": {
            "model": "bge-m3",
            "input": ""
        },
        "embedding_dimension": 1024
    },
    "OpenAI-Ada-002": {
        "type": "third_party_api",
        "model_name": "text-embedding-ada-002",
        "api_endpoint": "https://api.openai.com/v1/embeddings",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}" # Ensure OPENAI_API_KEY is set
        },
        "payload_template": {
            "model": "text-embedding-ada-002",
            "input": "" # Text will be injected here
        },
        "embedding_dimension": 1536
    },
    "OpenAI-Embedding-3-Small": {
        "type": "third_party_api",
        "model_name": "text-embedding-3-small",
        "api_endpoint": "https://api.openai.com/v1/embeddings",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"
        },
        "payload_template": {
            "model": "text-embedding-3-small",
            "input": "",
            # "dimensions": 512 # Optional: uncomment if you want a specific output dimension
        },
        "embedding_dimension": 1536 # Default max dimension for text-embedding-3-small
    },
}