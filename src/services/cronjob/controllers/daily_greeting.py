import asyncio
import threading

from fastapi import APIRouter, HTTPException

from src.bots.ai_bot import bot_app
from src.bots.handlers.good_morning import send_proactive_hello
from src.services.cronjob.services.daily_greeting_service import (
    get_all_conversation_references,
)

# Create FastAPI router
router = APIRouter(tags=["Cronjob Services"])


@router.get("/cronjob/daily-greeting", description="Send good morning messages to all users")
async def send_daily_greeting():
    """Send proactive good morning messages to all registered users."""
    references = get_all_conversation_references()
    if not references:
        raise HTTPException(status_code=404, detail="No conversation references found")

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tasks = [send_proactive_hello(bot_app.adapter, ref) for ref in references.values()]
        loop.run_until_complete(asyncio.gather(*tasks))
        loop.close()

    threading.Thread(target=run).start()
    return {"status": f"Sending proactive messages to {len(references)} users"}
