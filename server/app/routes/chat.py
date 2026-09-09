from fastapi import APIRouter, HTTPException, Depends
from typing import Annotated
from app.utils import ResponseFormatter
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas import ChatRequest
from app.models import SOPDocument
import httpx
from app.config import settings

router = APIRouter()

SYSTEM_PROMPT = (
    "You are a helpful credit assistant for CreditDataWatch. Answer the "
    "user's questions clearly, directly, and concisely using the "
    "information from the SOP document. Do not mention sections, guides, "
    "or 'according to' anything. Just give the answer."
)


async def _call_groq(message: str, context: str) -> str:
    """Free cloud fallback for environments without a local Ollama server
    (e.g. Render) — Groq's free tier needs no credit card. Raises on any
    failure so the caller's existing except-block handling (timeout /
    generic error messages) still applies uniformly regardless of which
    provider was actually used."""
    system_prompt = SYSTEM_PROMPT + (f"\n\n{context}" if context else "")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "content-type": "application/json",
            },
            json={
                "model": "openai/gpt-oss-20b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                ],
                "temperature": 0.7,
            },
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


@router.post("/chat")
async def chat(
    db: Annotated[AsyncSession, Depends(get_db)],
    req: ChatRequest
):
    message = req.message
    
    try:
        context = ""
        try:
            result = await db.execute(
                select(SOPDocument)
                .order_by(SOPDocument.uploaded_at.desc())
                .limit(1)
            )
            sop = result.scalar_one_or_none()
            if sop:
                context = f"Here is the SOP document for reference:\n{sop.content}\n\n"
        except Exception as e:
            print(f"Error fetching SOP: {str(e)}")
            pass

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": "llama3",
                        "prompt": f"{SYSTEM_PROMPT} {context}\n\nUser: {message}",
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    },
                    timeout=120.0
                )

                if response.status_code == 200:
                    ai_response = response.json().get("response", "")
                    return ResponseFormatter.create_success(data={"reply": ai_response})
                else:
                    print(f"Ollama returned status code: {response.status_code}")
                    print(f"Ollama response: {response.text}")
                    return ResponseFormatter.create_success(data={"reply": "I am having trouble connecting to my AI core right now. Please try again later."})

        except httpx.ConnectError:
            # No local Ollama server reachable (expected on Render and any
            # host without it installed) — fall back to the free Groq API
            # if a key is configured, rather than failing outright.
            if not settings.GROQ_API_KEY:
                print("Ollama connection error: Ollama is not running, and no GROQ_API_KEY is configured")
                return ResponseFormatter.create_success(data={"reply": "Ollama is not running. Please start Ollama on localhost:11434 to enable AI chat."})
            ai_response = await _call_groq(message, context)
            return ResponseFormatter.create_success(data={"reply": ai_response})

    except httpx.TimeoutException:
        print("AI chat timeout error")
        return ResponseFormatter.create_success(data={"reply": "The AI is taking too long to respond. Please try again."})
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print("Chat error:")
        print(error_msg)
        return ResponseFormatter.create_success(data={"reply": "An unexpected error occurred in the chat system. Please try again later."})
