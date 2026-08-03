"""AI assistant endpoint.

Read-only by design: every intent below only ever fetches data scoped to
the signed-in owner (via the same helpers/RLS the rest of the app uses).
Nothing the chatbot does can create, update or delete a record.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.chatbot import handlers, responses
from app.chatbot.nlu import analyse
from app.dependencies import AuthContext, require_api_user
from app.errors import AppError

router = APIRouter(prefix="/api/chatbot", tags=["chatbot"])
logger = logging.getLogger("chatbot")


class ChatIn(BaseModel):
    # A generous but bounded length: long enough for any real question,
    # short enough to make prompt-injection-style walls of text pointless
    # (there's no LLM here to inject into, but this also keeps queries fast).
    message: str = Field(min_length=1, max_length=500)


@router.post("/message")
async def chat(payload: ChatIn, user: AuthContext = Depends(require_api_user)):
    text = payload.message.strip()
    client, owner = user.client, user.user_id

    try:
        tenant_names = handlers.known_tenant_names(client, owner)
        property_names = handlers.known_property_names(client, owner)
        result = analyse(text, tenant_names=tenant_names, property_names=property_names)
        reply = _answer(client, owner, result)
        return {
            "reply": reply,
            "language": result.language,
            "intent": result.intent,
            "confidence": round(result.confidence, 2),
        }
    except AppError:
        raise
    except Exception:  # noqa: BLE001 - never leak internals to the chat window
        logger.exception("Chatbot failed to answer a message")
        language = "en"
        try:
            language = analyse(text).language
        except Exception:  # noqa: BLE001
            pass
        return {"reply": responses.error(language), "language": language, "intent": "error", "confidence": 0.0}


def _answer(client, owner, result) -> str:
    lang, intent, entities = result.language, result.intent, result.entities

    if intent == "greeting":
        return responses.greeting(lang)
    if intent == "help":
        return responses.help_message(lang)
    if intent == "renewal":
        return responses.renewal(lang, handlers.next_renewal(client, owner))
    if intent == "pending_rent":
        return responses.pending_rent(lang, handlers.pending_rent(client, owner))
    if intent == "vacant_property":
        return responses.vacant_properties(lang, handlers.vacant_properties(client, owner))
    if intent == "monthly_income":
        return responses.monthly_income(lang, handlers.monthly_income(client, owner))
    if intent == "payment_history":
        tenant = entities.get("tenant_name")
        return responses.payment_history(lang, handlers.payment_history(client, owner, tenant))
    if intent == "agreement_expiry":
        return responses.agreement_expiry(lang, handlers.expiring_agreements(client, owner))
    if intent == "overdue_rent":
        return responses.overdue_rent(lang, handlers.overdue_rent(client, owner))
    if intent == "property_info":
        prop = entities.get("property_name")
        return responses.property_info(lang, handlers.property_info(client, owner, prop))

    return responses.unknown(lang)
