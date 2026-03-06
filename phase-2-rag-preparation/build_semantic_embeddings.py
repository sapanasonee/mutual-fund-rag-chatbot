from sentence_transformers import SentenceTransformer
import json
import numpy as np

print("Loading embedding model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

texts = []
chunks = []

print("Reading corpus...")

with open("data/phase2/corpus.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        item = json.loads(line)
        texts.append(item["text"])
        chunks.append(item)

print("Creating embeddings...")

embeddings = model.encode(texts, show_progress_bar=True)

np.save("data/phase2/semantic_embeddings.npy", embeddings)

print("Embeddings saved successfully!")
