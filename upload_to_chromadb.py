import os
import json
import csv
import chromadb
from dotenv import load_dotenv

load_dotenv()

# 🔐 Load environment variables
CHROMA_API_KEY = os.getenv("CHROMA_CLOUD_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_CLOUD_TENANT")
CHROMA_DB = "DevHealth"
CHROMA_COLLECTION = "DevHealthInfo" 

if not CHROMA_API_KEY or not CHROMA_TENANT:
    raise EnvironmentError("Missing ChromaDB API key or Tenant ID.")

# 🔌 Connect to ChromaDB Cloud
client = chromadb.CloudClient(
    api_key=CHROMA_API_KEY,
    tenant=CHROMA_TENANT,
    database=CHROMA_DB
)

# 🧱 Storage for data
documents, metadatas, ids = [], [], []

# 📥 Process JSON
def process_json(path, tag):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for i, item in enumerate(data):
        q = item.get("Question", "").strip()
        r = item.get("Response", "").strip()
        cot = item.get("Complex_CoT", "").strip()
        if not q or not r:
            continue
        doc_text = f"Question: {q}\n\nThinking:\n{cot or 'N/A'}\n\nAnswer:\n{r}"
        documents.append(doc_text)
        metadatas.append({"source": tag, "type": "json"})
        ids.append(f"{tag}_doc_{i}")

# 📥 Process CSV
def process_csv(path, tag):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            q = row.get("question", "").strip()
            a = row.get("answer", "").strip()
            if not q or not a:
                continue
            doc_text = f"Question: {q}\n\nThinking:\nN/A\n\nAnswer:\n{a}"
            documents.append(doc_text)
            metadatas.append({"source": tag, "type": "csv"})
            ids.append(f"{tag}_doc_{i}")

# 📂 Load and process files
process_json("./MedicalInfo/MedicalQuestions.json", "json")
process_csv("./MedicalInfo/medquad.csv", "csv")

# 🧠 Upload to ChromaDB
collection = client.get_or_create_collection(name=CHROMA_COLLECTION)

batch_size = 100
for i in range(0, len(documents), batch_size):
    try:
        collection.add(
            documents=documents[i:i+batch_size],
            metadatas=metadatas[i:i+batch_size],
            ids=ids[i:i+batch_size]
        )
        print(f"✅ Uploaded batch {i//batch_size + 1}")
    except Exception as e:
        print(f"❌ Error in batch {i//batch_size + 1}: {e}")

print(f"🚀 Total uploaded: {len(documents)} documents to ChromaDB Cloud in collection '{CHROMA_COLLECTION}'.")
