import os
from pathlib import Path
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(title="NOX AI API", version="0.1.0")
ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = ROOT / "frontend" / "dist"


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    language: Literal["auto", "en", "hi", "ur", "hinglish"] = "auto"
    history: list[dict] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    mode: str


async def provider_reply(message: str, language: str, history: list[dict]) -> str | None:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None

    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
    messages = [
        {
            "role": "system",
            "content": (
                "You are NOX, a helpful, natural, concise multilingual assistant. "
                "Understand Hindi, Urdu, English, and Hinglish. Match the user's language "
                "when possible. Be honest about limitations and never claim actions you did not do. "
                f"Preferred language: {language}."
            ),
        }
    ]
    for item in history[-12:]:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and isinstance(content, str):
            messages.append({"role": role, "content": content[:4000]})
    messages.append({"role": "user", "content": message})

    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("APP_URL", "https://nox-ai.onrender.com"),
                "X-Title": "NOX AI",
            },
            json={"model": model, "messages": messages, "temperature": 0.7},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="AI provider request failed. Check the provider key/model and try again.")
    data = response.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="AI provider returned an unexpected response.")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "NOX AI", "ai_configured": bool(os.getenv("OPENROUTER_API_KEY"))}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest):
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        answer = await provider_reply(message, payload.language, payload.history)
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="The AI provider timed out. Please try again.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach the AI provider. Please try again.")
    if answer:
        return ChatResponse(reply=answer, mode="ai")
    return ChatResponse(
        reply=(
            "NOX is online in demo mode. To enable real AI responses, add an OPENROUTER_API_KEY "
            "environment variable in your hosting dashboard. I received your message: " + message
        ),
        mode="demo",
    )


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
