import chromadb
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
client = chromadb.Client()

def index_policy(doc_id, text):
    """Break policy into chunks and index them"""
    collection = client.get_or_create_collection(f"policy_{doc_id}")
    text = text or ""
    
    # Split into 500-word chunks
    words = text.split()
    chunks = [' '.join(words[i:i+500]) for i in range(0, len(words), 400)]
    chunks = [chunk for chunk in chunks if chunk.strip()]
    if not chunks:
        return
    
    embeddings = model.encode(chunks).tolist()
    collection.upsert(
        documents=chunks,
        embeddings=embeddings,
        ids=[f"chunk_{i}" for i in range(len(chunks))]
    )

def get_relevant_chunks(doc_id, question, n=3):
    """Get most relevant parts of policy for a question"""
    collection = client.get_or_create_collection(f"policy_{doc_id}")
    query_embedding = model.encode([question]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=n)
    documents = results.get('documents') or [[]]
    return '\n\n'.join(documents[0])
