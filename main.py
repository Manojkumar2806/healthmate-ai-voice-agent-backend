import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import logging
import chromadb
import google.generativeai as genai
import aiofiles
import requests

load_dotenv()
logging.basicConfig(level=logging.INFO)

CHROMA_API_KEY = os.getenv("CHROMA_CLOUD_API_KEY")
CHROMA_TENANT = os.getenv("CHROMA_CLOUD_TENANT")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
CHROMA_DB = "DevHealth"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# Clients
genai.configure(api_key=GEMINI_API_KEY)
chroma_client = chromadb.CloudClient(api_key=CHROMA_API_KEY, tenant=CHROMA_TENANT, database=CHROMA_DB)
collection = chroma_client.get_collection("DevHealthInfo")
gemini = genai.GenerativeModel("gemini-1.5-flash")

class QueryRequest(BaseModel):
    query: str
    n_results: int = 3

class QueryResponse(BaseModel):
    query: str
    thinking: str
    answer: str

@app.post("/api/query", response_model=QueryResponse)
async def query_devhealth(request: QueryRequest):
    try:
        results = collection.query(query_texts=[request.query], n_results=request.n_results)
        docs = [doc for doc in results["documents"][0]]
        context = "\n\n---\n\n".join(docs)

        # --- NEW: LLM prompt telling it exactly how to output HTML ---
        prompt = f"""
You are an expert clinical assistant AI. 
Based on the provided context, answer the user's question below.
Return your entire response as valid HTML (not Markdown).

Formatting rules:
- Use <p> for normal paragraphs/explanations.
- Use <ul>/<li> for bullet-point lists ONLY IF content naturally fits a list (differential dx, steps, criteria, etc).
- Use <b> for main points/headings.
- Use <i> for explanations, definitions, or details.
- It's fine to use <h4> or <h5> for subheadings if warranted.
- Do NOT force everything into a list—choose the best tags for each content chunk.
- "Thinking" and "Answer" may use lists, paragraphs, or a mix, as appropriate.

ALWAYS start the reasoning with 'Thinking:' and the final answer with 'Answer:' before the HTML, so these sections can be reliably parsed.

Context:
{context}

User Question:
{request.query}

Instructions:
Respond in raw HTML using the above guidelines.

Thinking:
<!-- Your reasoning goes here in HTML (use tags as instructed) -->

Answer:
<!-- Your final answer goes here in HTML (use tags as instructed) -->
"""
        # Get Gemini response
        result = gemini.generate_content(prompt).text.strip()
        if "Answer:" not in result:
            raise ValueError("Missing 'Answer:' section.")

        thinking_part, answer_part = result.split("Answer:", 1)
        return QueryResponse(
            query=request.query,
            thinking=thinking_part.replace("Thinking:", "").strip(),
            answer=answer_part.strip()
        )
    except Exception as e:
        logging.error(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


# ... Unchanged transcription code ...
@app.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    try:
        temp_path = f"/tmp/{audio.filename}"
        async with aiofiles.open(temp_path, 'wb') as out_file:
            content = await audio.read()
            await out_file.write(content)

        headers = {
            "authorization": ASSEMBLYAI_API_KEY
        }
        upload_response = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=headers,
            data=open(temp_path, 'rb')
        )
        audio_url = upload_response.json()["upload_url"]

        transcript_response = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers=headers,
            json={"audio_url": audio_url}
        )
        transcript_id = transcript_response.json()["id"]

        # Polling
        while True:
            polling = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=headers
            ).json()
            if polling["status"] == "completed":
                return {"text": polling["text"]}
            elif polling["status"] == "error":
                return {"text": "Transcription failed"}
    except Exception as e:
        logging.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail="Transcription failed")
