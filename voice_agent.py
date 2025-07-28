import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI
from livekit.agents import Agent, AgentSession
from livekit.plugins import assemblyai
from livekit.agents.llm import FunctionLLM
from livekit.agents.vad import SileroVAD

# Load environment variables
load_dotenv()
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")

# Configure AssemblyAI STT
stt = assemblyai.STT(
    api_key=ASSEMBLYAI_API_KEY,
    end_of_turn_confidence_threshold=0.7,
    min_end_of_turn_silence_when_confident=160,
    max_turn_silence=2400,
)

# Fallback LLM via HTTP call to FastAPI backend
def webhook_llm_function(prompt: str) -> str:
    try:
        response = requests.post("http://localhost:8000/api/query", json={"query": prompt})
        response.raise_for_status()
        return response.json().get("answer", "No answer received.")
    except Exception as e:
        return f"Error from LLM: {e}"

llm = FunctionLLM(func=webhook_llm_function)

# Create the LiveKit Agent
agent = Agent(
    name="HealthMate Voice Agent",
    session_factory=lambda: AgentSession(
        stt=stt,
        llm=llm,
        tts=None  # No TTS output
    ),
)

# Optional: for running with uvicorn if needed
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    print("Voice agent ready.")
