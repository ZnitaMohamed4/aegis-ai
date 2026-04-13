import os
import uuid
import logging
import chromadb 
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

# Load variables from .env to capture HF_TOKEN
load_dotenv()

logger = logging.getLogger(__name__)

# We use Sentences-Transformers to convert text to vectors.
# "all-MiniLM-L6-v2" is wildly fast and great for short messages like WhatsApp
try:
    logger.info("[SEMANTIC CACHE] Loading Embedding Model...")
    hf_token = os.getenv("HF_TOKEN")
    embedder = SentenceTransformer('all-MiniLM-L6-v2', token=hf_token)
except Exception as e:
    logger.error(f"[SEMANTIC CACHE] Error loading embedding model: {e}")
    embedder = None

# Initialize ChromaDB locally. It will create a folder called 'chroma_storage' in your backend dir
CHROMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'chroma_storage')
try:
    chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
    # We create a specific collection and explicitly set the distance metric to 'cosine'
    # 'aegis_moderation_cache_v2' is used to ensure old L2 vectors are cleanly discarded
    collection = chroma_client.get_or_create_collection(
        name="aegis_moderation_cache_v2",
        metadata={"hnsw:space": "cosine"}
    )
    logger.info("[SEMANTIC CACHE] ChromaDB initialized successfully!")
except Exception as e:
    logger.error(f"[SEMANTIC CACHE] Error initializing ChromaDB: {e}")
    collection = None

# Threshold for "how close is close enough?"
# 1.0 = exact same phrase. 0.82 = strong paraphrase. 0.70 = loose meaning match.
# Tune via .env: AEGIS_SEMANTIC_THRESHOLD (default: 0.82)
SIMILARITY_THRESHOLD = float(os.getenv('AEGIS_SEMANTIC_THRESHOLD', '0.82'))

def search_semantic_cache(text):
    """
    Given a message, convert it to a vector, and ask ChromaDB if we've seen something
    almost exactly like it before.
    """
    if not collection or not embedder:
        return None
        
    try:
        # 1. Convert the custom text into a 384-dimension vector!
        query_vector = embedder.encode(text).tolist()
        
        # 2. Query ChromaDB for the Top 1 most similar message
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=1,
            include=['metadatas', 'distances', 'documents']
        )
        
        # 3. Analyze the results
        if results['distances'] and results['distances'][0]:
            # Since we explicitly set hnsw:space to "cosine", Chroma returns "cosine distance" (which is 1.0 - Cosine Similarity).
            # To get an intuitive 0.0 to 1.0 similarity score back, we simply do 1.0 - distance
            distance = results['distances'][0][0]
            similarity_score = 1.0 - distance
            
            # 4. If the meaning is > 90% similar, we consider it a hit!
            if similarity_score >= SIMILARITY_THRESHOLD:
                metadata = results['metadatas'][0][0]
                matched_text = results['documents'][0][0]
                
                logger.info(f"[SEMANTIC HIT] Score: {similarity_score:.2f} | Matched: '{matched_text}'")
                
                # Reconstruct the prediction dictionary exactly like Groq would output it!
                return {
                    "is_harmful": metadata.get("is_harmful", metadata.get("decision", "BLOCK") != "ALLOW"),
                    "decision": metadata.get("decision", "BLOCK" if metadata.get("is_harmful") else "ALLOW"),
                    "category": metadata.get("category", "unknown"),
                    "confidence": metadata.get("confidence", 0.99),
                    "explanation": f"[Semantically cached based on: '{matched_text}'] {metadata.get('explanation', '')}"
                }
    except Exception as e:
        logger.error(f"[SEMANTIC CACHE] Search Error: {e}")
        
    return None

def add_to_semantic_cache(text, prediction_dict):
    """
    Saves a NEW Groq prediction to ChromaDB so we automatically bypass Groq next time.
    """
    if not collection or not embedder:
        return
        
    try:
        # Convert the new text to a vector
        vector = embedder.encode(text).tolist()
        
        # We need a unique ID for ChromaDB
        doc_id = str(uuid.uuid4())
        
        # Save the vector, the original text, and the Groq classification metadata
        is_harmful_val = prediction_dict.get("is_harmful")
        if is_harmful_val is None:
            is_harmful_val = prediction_dict.get("decision", "BLOCK").upper() != "ALLOW"
            
        collection.add(
            embeddings=[vector],
            documents=[text],
            metadatas=[{
                "is_harmful": is_harmful_val,
                "decision": prediction_dict.get("decision", "BLOCK" if is_harmful_val else "ALLOW").upper(),
                "category": prediction_dict.get("category", "unknown"),
                "confidence": prediction_dict.get("confidence", 0.99),
                "explanation": prediction_dict.get("explanation", "")
            }],
            ids=[doc_id]
        )
        logger.info(f"[SEMANTIC SAVE] Learned a new phrase: '{text[:30]}...'")
    except Exception as e:
        logger.error(f"[SEMANTIC CACHE] Add Error: {e}")
