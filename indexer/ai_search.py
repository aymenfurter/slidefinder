"""
Azure AI Search - Index management and document upload.

This module handles:
- Creating/deleting the search index
- Uploading documents from JSONL
- Generating embeddings using Azure OpenAI
- Verifying search functionality
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Generator, Optional
from concurrent.futures import ThreadPoolExecutor

import aiohttp
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    SearchableField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)

logger = logging.getLogger(__name__)


# --- Embedding Generation ---

async def generate_embedding_async(
    session: aiohttp.ClientSession,
    text: str,
    endpoint: str,
    api_key: str,
    deployment: str,
    semaphore: asyncio.Semaphore,
    max_retries: int = 5,
    base_delay: float = 1.0,
) -> Optional[list[float]]:
    """
    Generate embedding for a single text using Azure OpenAI with retry logic.
    
    Args:
        session: aiohttp session
        text: Text to embed
        endpoint: Azure OpenAI endpoint
        api_key: Azure OpenAI API key
        deployment: Embedding deployment name
        semaphore: Concurrency limiter
        max_retries: Maximum number of retries for rate limiting
        base_delay: Base delay for exponential backoff
    
    Returns:
        List of floats (embedding vector) or None on error
    """
    async with semaphore:
        url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings?api-version=2024-06-01"
        
        headers = {
            "Content-Type": "application/json",
            "api-key": api_key,
        }
        
        # Truncate text if too long (max ~8000 tokens for ada-002)
        max_chars = 30000  # ~7500 tokens
        if len(text) > max_chars:
            text = text[:max_chars]
        
        payload = {
            "input": text,
        }
        
        for attempt in range(max_retries):
            try:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["data"][0]["embedding"]
                    elif resp.status == 429:
                        # Rate limited - get retry-after header or use exponential backoff
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            delay = float(retry_after)
                        else:
                            delay = base_delay * (2 ** attempt) + (asyncio.get_event_loop().time() % 1)
                        
                        if attempt < max_retries - 1:
                            await asyncio.sleep(delay)
                            continue
                        else:
                            return None
                    else:
                        error_text = await resp.text()
                        logger.warning(f"Embedding API error {resp.status}: {error_text[:200]}")
                        return None
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    await asyncio.sleep(delay)
                    continue
                logger.warning(f"Embedding request failed after {max_retries} attempts: {e}")
                return None
        
        return None


async def generate_embeddings_batch(
    documents: list[dict],
    azure_openai_endpoint: str,
    azure_openai_api_key: str,
    azure_openai_deployment: str = "text-embedding-ada-002",
    max_parallel: int = 30,
    content_field: str = "content",
    vector_field: str = "content_vector",
) -> list[dict]:
    """
    Generate embeddings for a batch of documents in parallel.
    
    Args:
        documents: List of document dicts
        azure_openai_endpoint: Azure OpenAI endpoint
        azure_openai_api_key: Azure OpenAI API key
        azure_openai_deployment: Embedding deployment name
        max_parallel: Maximum parallel requests
        content_field: Field name containing text to embed
        vector_field: Field name to store embedding vector
    
    Returns:
        List of documents with embeddings added
    """
    semaphore = asyncio.Semaphore(max_parallel)
    connector = aiohttp.TCPConnector(limit=max_parallel + 5)
    timeout = aiohttp.ClientTimeout(total=300)  # Long timeout to allow for retries
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []
        for doc in documents:
            text = doc.get(content_field, "") or ""
            # Combine title and content for better embeddings
            title = doc.get("title", "") or ""
            combined_text = f"{title}\n\n{text}" if title else text
            
            task = generate_embedding_async(
                session=session,
                text=combined_text,
                endpoint=azure_openai_endpoint,
                api_key=azure_openai_api_key,
                deployment=azure_openai_deployment,
                semaphore=semaphore,
            )
            tasks.append(task)
        
        embeddings = await asyncio.gather(*tasks)
    
    # Add embeddings to documents
    for doc, embedding in zip(documents, embeddings):
        if embedding:
            doc[vector_field] = embedding
        else:
            # Use empty vector if embedding failed
            doc[vector_field] = None
    
    return documents


def generate_embeddings_sync(
    documents: list[dict],
    azure_openai_endpoint: str,
    azure_openai_api_key: str,
    azure_openai_deployment: str = "text-embedding-ada-002",
    max_parallel: int = 30,
) -> list[dict]:
    """
    Synchronous wrapper for embedding generation.
    
    Args:
        documents: List of document dicts
        azure_openai_endpoint: Azure OpenAI endpoint
        azure_openai_api_key: Azure OpenAI API key
        azure_openai_deployment: Embedding deployment name
        max_parallel: Maximum parallel requests
    
    Returns:
        List of documents with embeddings added
    """
    return asyncio.run(generate_embeddings_batch(
        documents=documents,
        azure_openai_endpoint=azure_openai_endpoint,
        azure_openai_api_key=azure_openai_api_key,
        azure_openai_deployment=azure_openai_deployment,
        max_parallel=max_parallel,
    ))


# --- Index Management ---

def get_index_client(endpoint: str, api_key: str) -> SearchIndexClient:
    """Create a Search Index client."""
    return SearchIndexClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(api_key)
    )


def get_search_client(endpoint: str, api_key: str, index_name: str) -> SearchClient:
    """Create a Search client."""
    return SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(api_key)
    )


def create_index(
    endpoint: str,
    api_key: str,
    index_name: str,
    delete_first: bool = False,
    azure_openai_endpoint: str = None,
    azure_openai_api_key: str = None,
    azure_openai_embedding_deployment: str = "text-embedding-ada-002",
    azure_openai_model_name: str = "text-embedding-ada-002",
) -> bool:
    """
    Create the Azure AI Search index with vector search and semantic configuration.
    
    Args:
        endpoint: Azure Search endpoint
        api_key: Azure Search API key
        index_name: Name of the index
        delete_first: Delete existing index before creating
        azure_openai_endpoint: Azure OpenAI endpoint for vectorizer
        azure_openai_api_key: Azure OpenAI API key for vectorizer
        azure_openai_embedding_deployment: Azure OpenAI embedding deployment name
        azure_openai_model_name: Azure OpenAI embedding model name
    
    Returns:
        True if successful
    """
    client = get_index_client(endpoint, api_key)
    
    # Check if index exists
    existing = [idx.name for idx in client.list_indexes()]
    
    if index_name in existing:
        if delete_first:
            logger.info(f"Deleting existing index '{index_name}'...")
            client.delete_index(index_name)
        else:
            logger.warning(f"Index '{index_name}' already exists")
            return True
    
    # Define schema with vector field
    fields = [
        SimpleField(
            name="slide_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
            sortable=True,
        ),
        SimpleField(
            name="session_code",
            type=SearchFieldDataType.String,
            filterable=True,
            sortable=True,
            facetable=True,
        ),
        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SimpleField(
            name="slide_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
            searchable=True,
        ),
        SimpleField(
            name="event",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="session_url",
            type=SearchFieldDataType.String,
        ),
        SimpleField(
            name="ppt_url",
            type=SearchFieldDataType.String,
        ),
        # Vector field for embeddings
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,  # text-embedding-ada-002 dimensions
            vector_search_profile_name="vector-profile",
        ),
    ]
    
    # Configure vector search with integrated vectorizer
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hnsw-algorithm",
            ),
        ],
        profiles=[
            VectorSearchProfile(
                name="vector-profile",
                algorithm_configuration_name="hnsw-algorithm",
                vectorizer_name="openai-vectorizer" if azure_openai_endpoint else None,
            ),
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name="openai-vectorizer",
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=azure_openai_endpoint,
                    deployment_name=azure_openai_embedding_deployment,
                    model_name=azure_openai_model_name,
                    api_key=azure_openai_api_key,
                ),
            ),
        ] if azure_openai_endpoint else [],
    )
    
    # Configure semantic search
    semantic_config = SemanticConfiguration(
        name="semantic-config",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            content_fields=[SemanticField(field_name="content")],
            keywords_fields=[
                SemanticField(field_name="session_code"),
                SemanticField(field_name="event"),
            ],
        ),
    )
    
    semantic_search = SemanticSearch(
        default_configuration_name="semantic-config",
        configurations=[semantic_config],
    )
    
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
    
    logger.info(f"Creating index '{index_name}' with vector search and semantic configuration...")
    client.create_or_update_index(index)
    logger.info("Index created successfully")
    
    return True


def delete_index(endpoint: str, api_key: str, index_name: str) -> bool:
    """Delete the search index."""
    client = get_index_client(endpoint, api_key)
    
    existing = [idx.name for idx in client.list_indexes()]
    
    if index_name not in existing:
        logger.warning(f"Index '{index_name}' does not exist")
        return False
    
    logger.info(f"Deleting index '{index_name}'...")
    client.delete_index(index_name)
    logger.info("Index deleted")
    
    return True


def load_documents(jsonl_path: Path) -> Generator[dict, None, None]:
    """Load documents from JSONL file."""
    if not jsonl_path.exists():
        logger.error(f"File not found: {jsonl_path}")
        return
    
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid JSON at line {line_num}: {e}")


def upload_documents(
    endpoint: str,
    api_key: str,
    index_name: str,
    jsonl_path: Path,
    batch_size: int = 500,
    azure_openai_endpoint: str = None,
    azure_openai_api_key: str = None,
    azure_openai_deployment: str = "text-embedding-ada-002",
    max_parallel_embeddings: int = 30,
) -> tuple[int, int]:
    """
    Upload documents to Azure AI Search with optional embedding generation.
    
    Args:
        endpoint: Azure Search endpoint
        api_key: Azure Search API key
        index_name: Name of the index
        jsonl_path: Path to JSONL file
        batch_size: Documents per batch
        azure_openai_endpoint: Azure OpenAI endpoint for embeddings (optional)
        azure_openai_api_key: Azure OpenAI API key for embeddings (optional)
        azure_openai_deployment: Azure OpenAI embedding deployment name
        max_parallel_embeddings: Max parallel embedding requests
    
    Returns:
        Tuple of (successful, failed) counts
    """
    client = get_search_client(endpoint, api_key, index_name)
    
    # Load all documents
    docs = list(load_documents(jsonl_path))
    total = len(docs)
    
    if total == 0:
        logger.warning("No documents to upload")
        return 0, 0
    
    # Check if we should generate embeddings
    generate_embeddings = bool(azure_openai_endpoint and azure_openai_api_key)
    
    if generate_embeddings:
        logger.info(f"Will generate embeddings using {azure_openai_deployment} ({max_parallel_embeddings} parallel requests)")
    
    logger.info(f"Uploading {total:,} documents in batches of {batch_size}")
    
    successful = 0
    failed = 0
    
    for i in range(0, total, batch_size):
        batch = docs[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total + batch_size - 1) // batch_size
        
        # Generate embeddings for this batch if configured
        if generate_embeddings:
            logger.info(f"Batch {batch_num}/{total_batches}: Generating {len(batch)} embeddings...")
            batch = generate_embeddings_sync(
                documents=batch,
                azure_openai_endpoint=azure_openai_endpoint,
                azure_openai_api_key=azure_openai_api_key,
                azure_openai_deployment=azure_openai_deployment,
                max_parallel=max_parallel_embeddings,
            )
            
            # Count how many embeddings were generated
            embeddings_generated = sum(1 for doc in batch if doc.get("content_vector"))
            logger.info(f"  Generated {embeddings_generated}/{len(batch)} embeddings")
            
            # Remove None vectors (failed embeddings) - search will still work without them
            for doc in batch:
                if doc.get("content_vector") is None:
                    doc.pop("content_vector", None)
        
        try:
            result = client.upload_documents(documents=batch)
            
            batch_success = sum(1 for r in result if r.succeeded)
            batch_failed = sum(1 for r in result if not r.succeeded)
            
            successful += batch_success
            failed += batch_failed
            
            progress = (i + len(batch)) / total * 100
            logger.info(f"Batch {batch_num}/{total_batches}: {batch_success} ok, {batch_failed} failed ({progress:.1f}%)")
            
            # Log failures
            for r in result:
                if not r.succeeded:
                    logger.warning(f"  Failed: {r.key} - {r.error_message}")
                    
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")
            failed += len(batch)
    
    logger.info(f"Upload complete: {successful:,} successful, {failed:,} failed")
    return successful, failed


def verify_index(
    endpoint: str,
    api_key: str,
    index_name: str,
    test_queries: Optional[list[str]] = None
) -> bool:
    """
    Verify the search index works correctly.
    
    Args:
        endpoint: Azure Search endpoint
        api_key: Azure Search API key
        index_name: Name of the index
        test_queries: Optional list of test queries
    
    Returns:
        True if all tests pass
    """
    client = get_search_client(endpoint, api_key, index_name)
    
    # Check document count
    try:
        result = client.search(search_text="*", include_total_count=True)
        count = result.get_count()
        logger.info(f"Documents in index: {count:,}")
        
        if count == 0:
            logger.warning("Index is empty!")
            return False
            
    except Exception as e:
        logger.error(f"Failed to get document count: {e}")
        return False
    
    # Run test queries
    test_queries = test_queries or ["AI", "Azure", "cloud"]
    
    for query in test_queries:
        try:
            result = client.search(
                search_text=query,
                include_total_count=True,
                top=5
            )
            hits = result.get_count()
            
            # Get first result
            first = None
            for doc in result:
                first = doc
                break
            
            if first:
                logger.info(f"Query '{query}': {hits:,} hits, top: {first.get('title', 'N/A')[:50]}")
            else:
                logger.info(f"Query '{query}': {hits:,} hits (no results)")
                
        except Exception as e:
            logger.error(f"Query '{query}' failed: {e}")
            return False
    
    logger.info("All verification tests passed")
    return True


def get_index_stats(endpoint: str, api_key: str, index_name: str) -> dict:
    """Get statistics about the index."""
    stats = {
        "exists": False,
        "document_count": 0,
        "fields": []
    }
    
    index_client = get_index_client(endpoint, api_key)
    
    # Check if exists
    existing = [idx.name for idx in index_client.list_indexes()]
    if index_name not in existing:
        return stats
    
    stats["exists"] = True
    
    # Get index details
    index = index_client.get_index(index_name)
    stats["fields"] = [
        {
            "name": f.name,
            "type": str(f.type),
            "searchable": getattr(f, 'searchable', False),
            "filterable": getattr(f, 'filterable', False),
        }
        for f in index.fields
    ]
    
    # Get document count
    search_client = get_search_client(endpoint, api_key, index_name)
    try:
        result = search_client.search(search_text="*", include_total_count=True)
        stats["document_count"] = result.get_count()
    except Exception:
        pass
    
    return stats


def setup_knowledge_source(
    endpoint: str,
    api_key: str,
    index_name: str,
    knowledge_source_name: str = "slidefinder-ks",
) -> bool:
    """
    Create or update the knowledge source for agentic retrieval.
    
    This configures which fields are returned in search results.
    
    Args:
        endpoint: Azure Search endpoint
        api_key: Azure Search API key
        index_name: Name of the search index
        knowledge_source_name: Name for the knowledge source
    
    Returns:
        True if successful
    """
    import requests
    
    endpoint = endpoint.rstrip('/')
    url = f"{endpoint}/knowledgeSources('{knowledge_source_name}')?api-version=2025-11-01-preview"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    payload = {
        "name": knowledge_source_name,
        "kind": "searchIndex",
        "description": "Knowledge source for Microsoft Build and Ignite presentation slides.",
        "searchIndexParameters": {
            "searchIndexName": index_name,
            "semanticConfigurationName": "semantic-config",
            "sourceDataFields": [
                {"name": "slide_id"},
                {"name": "title"},
                {"name": "session_code"},
                {"name": "slide_number"},
                {"name": "event"},
                {"name": "session_url"},
                {"name": "ppt_url"},
                {"name": "content"}
            ],
            "searchFields": [
                {"name": "content"},
                {"name": "title"}
            ]
        }
    }
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in (200, 201, 204):
            logger.info(f"Knowledge source '{knowledge_source_name}' configured successfully")
            return True
        else:
            logger.error(f"Failed to configure knowledge source: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error configuring knowledge source: {e}")
        return False


def setup_knowledge_base(
    endpoint: str,
    api_key: str,
    knowledge_base_name: str = "slidefinder-kb",
    knowledge_source_name: str = "slidefinder-ks",
    azure_openai_endpoint: str = None,
    azure_openai_api_key: str = None,
    azure_openai_deployment: str = "gpt-4o-mini",
) -> bool:
    """
    Create or update the knowledge base for agentic retrieval.
    
    Args:
        endpoint: Azure Search endpoint
        api_key: Azure Search API key
        knowledge_base_name: Name for the knowledge base
        knowledge_source_name: Name of the knowledge source to use
        azure_openai_endpoint: Azure OpenAI endpoint for reasoning model
        azure_openai_api_key: Azure OpenAI API key
        azure_openai_deployment: Azure OpenAI deployment name (e.g., gpt-4o-mini)
    
    Returns:
        True if successful
    """
    import requests
    
    endpoint = endpoint.rstrip('/')
    url = f"{endpoint}/knowledgeBases('{knowledge_base_name}')?api-version=2025-11-01-preview"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    
    payload = {
        "name": knowledge_base_name,
        "description": "SlideFinder knowledge base for Microsoft Build and Ignite slides",
        "knowledgeSources": [
            {
                "name": knowledge_source_name
            }
        ]
    }
    
    # Add model configuration if Azure OpenAI credentials provided
    if azure_openai_endpoint and azure_openai_api_key:
        openai_endpoint = azure_openai_endpoint.rstrip('/')
        payload["models"] = [
            {
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": openai_endpoint,
                    "deploymentId": azure_openai_deployment,
                    "apiKey": azure_openai_api_key,
                    "modelName": azure_openai_deployment
                }
            }
        ]
        logger.info(f"Configuring knowledge base with model: {azure_openai_deployment}")
    
    try:
        response = requests.put(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code in (200, 201, 204):
            logger.info(f"Knowledge base '{knowledge_base_name}' configured successfully")
            return True
        else:
            logger.error(f"Failed to configure knowledge base: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error configuring knowledge base: {e}")
        return False
