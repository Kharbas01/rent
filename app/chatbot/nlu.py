"""Lightweight rule-based NLU: language detection + intent classification.

No external ML/AI service is called. This is intentional — it keeps the
assistant fast, free, and fully private (nothing about a landlord's tenants
or finances ever leaves the server). Typo tolerance comes from Python's
built-in `difflib`, and synonym coverage comes from generous keyword lists
per intent, in English, Hindi (Devanagari) and Hinglish (romanised Hindi).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
WORD_RE = re.compile(r"[a-zA-Z\u0900-\u097F]+")

# Romanised Hindi/Hinglish function words — presence of these (with no
# Devanagari script) signals "Hinglish" rather than plain English.
HINGLISH_MARKERS = {
    "kal", "aaj", "kaunsi", "konsi", "kaun", "kisne", "kisका", "kitna", "kitne",
    "kab", "kya", "hai", "hain", "nahi", "nahin", "diya", "diye", "de", "do",
    "wala", "waala", "walla", "khali", "abhi", "kro", "karo", "batao", "bata",
    "dikhao", "dikha", "chahiye", "mera", "meri", "mujhe", "humara", "hamara",
    "tenant", "ka", "ki", "ke", "se", "me", "mein", "koi", "hua", "hui", "rha",
    "raha", "rahe",
}


@dataclass
class NluResult:
    language: str  # "en" | "hi" | "hinglish"
    intent: str
    confidence: float
    entities: dict = field(default_factory=dict)


def detect_language(text: str) -> str:
    if DEVANAGARI_RE.search(text):
        return "hi"
    words = {w.lower() for w in WORD_RE.findall(text)}
    if words & HINGLISH_MARKERS:
        return "hinglish"
    return "en"


def _normalise(text: str) -> str:
    return re.sub(r"[^\w\s\u0900-\u097F]", " ", text.lower()).strip()


# Each intent maps to a list of keyword phrases (English, Hindi, Hinglish
# mixed together) — any single phrase match is a strong signal, so this
# doubles as a synonym dictionary without needing a translation model.
INTENT_KEYWORDS: dict[str, list[str]] = {
    "renewal": [
        "next agreement renewal", "next renewal", "agreement renew", "renewal date",
        "next contract", "contract renew", "agreement kab renew", "kab renew hoga",
        "renew hone wala", "renewal kab hai", "agreement kab khatam",
        "अगला रिन्यूअल", "एग्रीमेंट रिन्यू", "अगला एग्रीमेंट", "रिन्यूअल डेट", "कब रिन्यू होगा",
    ],
    "pending_rent": [
        "pending rent", "rent nahi diya", "pending payment", "rent due",
        "outstanding rent", "kisne rent nahi diya", "due rent", "kis kis ka rent baaki",
        "rent baaki", "rent pending", "kis tenant ka rent due",
        "पेंडिंग रेंट", "रेंट ड्यू", "रेंट नहीं दिया", "किसने रेंट नहीं दिया", "रेंट बाकी",
    ],
    "vacant_property": [
        "vacant property", "empty flat", "available propert", "koi room khali",
        "available shop", "khali hai", "vacant flat", "kaunsi property khali",
        "kaun sa flat khali", "empty room", "available flat", "property vacant hai",
        "खाली प्रॉपर्टी", "कौनसी प्रॉपर्टी खाली है", "खाली फ्लैट", "प्रॉपर्टी खाली",
    ],
    "monthly_income": [
        "monthly income", "this month income", "income report", "kitna rent collect",
        "total collection", "collection kitna", "is mahine ka income",
        "is month kitna aaya", "revenue this month",
        "इस महीने की इनकम", "मासिक आय", "कितना रेंट कलेक्ट हुआ", "इनकम रिपोर्ट",
    ],
    "payment_history": [
        "payment history", "last payment", "payment details", "tenant payment history",
        "purana payment", "payment record", "pichla payment", "kitna paisa diya",
        "पेमेंट हिस्ट्री", "पिछला पेमेंट", "पेमेंट डिटेल्स",
    ],
    "agreement_expiry": [
        "expiring agreement", "agreement expiry", "expiry list", "agreements expiring",
        "is mahine kaunse agreement khatam", "expire hone wale agreement",
        "एग्रीमेंट एक्सपायरी", "एक्सपायर हो रहे एग्रीमेंट", "एग्रीमेंट खत्म",
    ],
    "overdue_rent": [
        "overdue rent", "late payment", "defaulter", "late tenant", "rent overdue",
        "kitna din se rent nahi diya", "sabse zyada late",
        "ओवरड्यू रेंट", "लेट पेमेंट", "डिफॉल्टर",
    ],
    "property_info": [
        "property detail", "property information", "show property", "owner detail",
        "property ki jankari", "flat detail", "shop detail", "property ke bare",
        "प्रॉपर्टी की जानकारी", "प्रॉपर्टी डिटेल", "प्रॉपर्टी की डिटेल्स",
    ],
    "greeting": [
        "hi", "hello", "hey", "namaste", "namaskar", "good morning", "good evening",
        "नमस्ते", "नमस्कार",
    ],
    "help": [
        "help", "what can you do", "kya kar sakte ho", "kya kar sakti ho",
        "commands", "options", "kya kar sakta hai",
        "मदद", "क्या कर सकते हो",
    ],
}

_ALL_PHRASES = [(intent, phrase) for intent, phrases in INTENT_KEYWORDS.items() for phrase in phrases]


def classify_intent(text: str) -> tuple[str, float]:
    """Return (intent, confidence 0-1). Falls back to 'unknown' below threshold."""
    normalised = _normalise(text)
    if not normalised:
        return "unknown", 0.0

    best_intent, best_score = "unknown", 0.0

    for intent, phrase in _ALL_PHRASES:
        if phrase in normalised:
            # Exact substring match on a multi-word phrase is a very strong signal.
            score = 0.6 + 0.1 * min(len(phrase.split()), 4)
            if score > best_score:
                best_intent, best_score = intent, min(score, 0.98)

    if best_score >= 0.6:
        return best_intent, best_score

    # Fuzzy fallback for typos / slightly-off phrasing: compare the whole
    # message against each phrase with difflib's ratio.
    for intent, phrase in _ALL_PHRASES:
        ratio = difflib.SequenceMatcher(None, normalised, phrase).ratio()
        if ratio > best_score:
            best_intent, best_score = intent, ratio

    if best_score < 0.45:
        return "unknown", best_score
    return best_intent, best_score


def extract_entity(text: str, candidates: list[str]) -> str | None:
    """Fuzzy-match a tenant/property name mentioned in the message against a
    known list of names (typo-tolerant). Returns the best candidate or None."""
    if not candidates:
        return None
    normalised = _normalise(text)
    words = normalised.split()

    # 1) direct substring match (fast path, handles multi-word names).
    for name in candidates:
        if name.lower() in normalised:
            return name

    # 2) fuzzy match each candidate's first word against message tokens.
    best_name, best_ratio = None, 0.0
    for name in candidates:
        first_token = name.lower().split()[0]
        for word in words:
            ratio = difflib.SequenceMatcher(None, word, first_token).ratio()
            if ratio > best_ratio:
                best_name, best_ratio = name, ratio

    return best_name if best_ratio >= 0.75 else None


def analyse(text: str, tenant_names: list[str] | None = None, property_names: list[str] | None = None) -> NluResult:
    language = detect_language(text)
    intent, confidence = classify_intent(text)

    entities: dict = {}
    if intent in ("payment_history",):
        tenant = extract_entity(text, tenant_names or [])
        if tenant:
            entities["tenant_name"] = tenant
    if intent in ("property_info",):
        prop = extract_entity(text, property_names or [])
        if prop:
            entities["property_name"] = prop

    return NluResult(language=language, intent=intent, confidence=confidence, entities=entities)
