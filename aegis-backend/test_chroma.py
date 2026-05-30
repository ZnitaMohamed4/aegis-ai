import os
import chromadb
from sentence_transformers import SentenceTransformer

# Setup ChromaDB
chroma_path = os.path.join('/home/muhammed/Desktop/aegis-ai/aegis-backend/chroma_storage')
client = chromadb.PersistentClient(path=chroma_path)
collection = client.get_or_create_collection(name="aegis_knowledge_base", metadata={"hnsw:space": "cosine"})

print(f"Total chunks in collection: {collection.count()}")

# Get some metadata
res = collection.get(limit=5)
print("Sample metadatas:", res['metadatas'])

# Load embedder
embedder = SentenceTransformer('all-MiniLM-L6-v2')
query = "donnez moi un resumee sur la loi 09-08?"
vector = embedder.encode(query).tolist()

results = collection.query(
    query_embeddings=[vector],
    n_results=4,
    where={"language": "fr"}
)
print("Search results:")
for i, doc in enumerate(results['documents'][0]):
    print(f"\n--- Result {i+1} (Distance: {results['distances'][0][i]}) ---")
    print(doc[:200])

