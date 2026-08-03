"""Turns the raw data from handlers.py into natural, conversational replies
in the same language the user asked in (English / Hindi / Hinglish)."""

from __future__ import annotations

from datetime import date


def money(amount: float) -> str:
    return f"\u20b9{amount:,.0f}"


def _fmt_date(d) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%d %B %Y")


def greeting(language: str) -> str:
    if language == "hi":
        return "नमस्ते! मैं आपका रेंट मैनेजमेंट असिस्टेंट हूँ। रेंट, टेनेंट, प्रॉपर्टी या पेमेंट के बारे में कुछ भी पूछें।"
    if language == "hinglish":
        return "Namaste! Main aapka rent management assistant hoon. Rent, tenant, property ya payment ke baare mein kuch bhi puchiye."
    return "Hi! I'm your rent management assistant. Ask me anything about rent, tenants, properties or payments."


def help_message(language: str) -> str:
    examples = [
        "Next agreement renewal",
        "Pending rent",
        "Vacant properties",
        "This month's income",
        "Rahul's payment history",
        "Expiring agreements",
        "Overdue rent",
        "Flat A101 details",
    ]
    bullet = "\n".join(f"• {e}" for e in examples)
    if language == "hi":
        return f"मैं इन सवालों में मदद कर सकता हूँ:\n{bullet}"
    if language == "hinglish":
        return f"Main in cheezon mein help kar sakta hoon:\n{bullet}"
    return f"I can help with things like:\n{bullet}"


def unknown(language: str) -> str:
    if language == "hi":
        return "माफ़ कीजिए, मुझे यह समझ नहीं आया। कृपया दोबारा पूछें — जैसे \"pending rent\" या \"vacant properties\"।"
    if language == "hinglish":
        return "Sorry, samajh nahi aaya. Thoda alag tarike se puchiye — jaise \"pending rent\" ya \"vacant properties\"."
    return "Sorry, I didn't quite get that. Try asking things like \"pending rent\" or \"vacant properties\"."


def error(language: str) -> str:
    if language == "hi":
        return "माफ़ कीजिए, अभी जवाब देने में कोई दिक्कत आ गई। कृपया थोड़ी देर बाद कोशिश करें।"
    if language == "hinglish":
        return "Sorry, abhi jawab dene mein dikkat aa gayi. Thodi der baad phir try kijiye."
    return "Sorry, something went wrong while looking that up. Please try again in a moment."


def renewal(language: str, data: dict | None) -> str:
    if not data:
        if language == "hi":
            return "अभी किसी भी टेनेंट का कोई अपकमिंग एग्रीमेंट रिन्यूअल नहीं है।"
        if language == "hinglish":
            return "Abhi koi bhi tenant ka upcoming agreement renewal nahi hai."
        return "There's no upcoming agreement renewal right now."

    d, days = _fmt_date(data["renewal_date"]), data["days_remaining"]
    if language == "hi":
        return f"{data['property']} का एग्रीमेंट {data['tenant']} के साथ {d} को रिन्यू होना है ({days} दिन बचे हैं)।"
    if language == "hinglish":
        return f"{data['property']} ka agreement {data['tenant']} ke saath {d} ko renew hona hai ({days} din baaki hain)."
    return f"{data['property']}'s agreement with {data['tenant']} renews on {d} ({days} days remaining)."


def pending_rent(language: str, data: dict) -> str:
    if not data["items"]:
        if language == "hi":
            return "बढ़िया खबर — कोई पेंडिंग रेंट नहीं है, सभी टेनेंट अप टू डेट हैं!"
        if language == "hinglish":
            return "Good news — koi pending rent nahi hai, sab tenants up to date hain!"
        return "Good news — there's no pending rent, all tenants are up to date!"

    lines = [f"• {i['tenant']} ({i['property']}): {money(i['amount'])}" for i in data["items"]]
    body = "\n".join(lines)
    total = money(data["total"])
    if language == "hi":
        return f"{data['count']} टेनेंट का रेंट पेंडिंग है, कुल {total}:\n{body}"
    if language == "hinglish":
        return f"{data['count']} tenants ka rent pending hai, total {total}:\n{body}"
    return f"{data['count']} tenant(s) have pending rent, totalling {total}:\n{body}"


def vacant_properties(language: str, items: list[dict]) -> str:
    if not items:
        if language == "hi":
            return "अभी कोई भी प्रॉपर्टी खाली नहीं है — सब ऑक्यूपाइड हैं।"
        if language == "hinglish":
            return "Abhi koi bhi property khali nahi hai — sab occupied hain."
        return "No properties are vacant right now — everything is occupied."

    lines = [f"• {p['name']} ({p['type']}, {p['location']}) — {money(p['rent'])}/mo" for p in items]
    body = "\n".join(lines)
    word_en = "property" if len(items) == 1 else "properties"
    if language == "hi":
        return f"अभी {len(items)} प्रॉपर्टी खाली हैं:\n{body}"
    if language == "hinglish":
        return f"Abhi {len(items)} {word_en} khali hain:\n{body}"
    return f"There are {len(items)} vacant {word_en} right now:\n{body}"


def monthly_income(language: str, data: dict) -> str:
    due, collected, pending, pct = money(data["total_due"]), money(data["collected"]), money(data["pending"]), data["collection_pct"]
    if language == "hi":
        return (
            f"इस महीने कुल {due} में से {collected} कलेक्ट हुआ है ({pct}%), "
            f"और {pending} अभी भी पेंडिंग है।"
        )
    if language == "hinglish":
        return f"Is mahine total {due} mein se {collected} collect hua hai ({pct}%), aur {pending} abhi bhi pending hai."
    return f"This month, {collected} has been collected out of {due} due ({pct}%), with {pending} still pending."


def payment_history(language: str, data: dict) -> str:
    if not data["items"]:
        who = data.get("tenant")
        if language == "hi":
            return f"{who + ' का ' if who else ''}कोई पेमेंट रिकॉर्ड नहीं मिला।"
        if language == "hinglish":
            return f"{(who + ' ka ') if who else ''}Koi payment record nahi mila."
        return f"No payment history found{' for ' + who if who else ''}."

    lines = [
        f"• {i['date'] or '—'}: {money(i['amount'])} via {i['method']} ({i['status']}) — Ref #{i['reference']}"
        for i in data["items"]
    ]
    body = "\n".join(lines)
    who = data.get("tenant")
    if language == "hi":
        return f"{who + ' की ' if who else ''}पिछली {len(data['items'])} पेमेंट्स:\n{body}"
    if language == "hinglish":
        return f"{(who + ' ki ') if who else ''}Last {len(data['items'])} payments:\n{body}"
    lead = f"Here are {who}'s" if who else "Here are the"
    return f"{lead} last {len(data['items'])} payments:\n{body}"


def agreement_expiry(language: str, items: list[dict]) -> str:
    if not items:
        if language == "hi":
            return "इस महीने कोई भी एग्रीमेंट एक्सपायर नहीं हो रहा।"
        if language == "hinglish":
            return "Is mahine koi bhi agreement expire nahi ho raha."
        return "No agreements are expiring this month."

    lines = [
        f"• {i['tenant']} ({i['property']}): {_fmt_date(i['expiry_date'])}, {i['days_remaining']} days — {i['status']}"
        for i in items
    ]
    body = "\n".join(lines)
    if language == "hi":
        return f"इस महीने {len(items)} एग्रीमेंट एक्सपायर हो रहे हैं:\n{body}"
    if language == "hinglish":
        return f"Is mahine {len(items)} agreements expire ho rahe hain:\n{body}"
    return f"{len(items)} agreement(s) are expiring this month:\n{body}"


def overdue_rent(language: str, items: list[dict]) -> str:
    if not items:
        if language == "hi":
            return "कोई भी टेनेंट रेंट में लेट नहीं है — सब क्लियर है!"
        if language == "hinglish":
            return "Koi bhi tenant rent mein late nahi hai — sab clear hai!"
        return "No tenants are overdue on rent — everything is clear!"

    lines = [f"• {i['tenant']} ({i['property']}): {money(i['amount'])}, {i['overdue_days']} days overdue" for i in items]
    body = "\n".join(lines)
    if language == "hi":
        return f"{len(items)} टेनेंट रेंट में लेट हैं:\n{body}"
    if language == "hinglish":
        return f"{len(items)} tenants rent mein late hain:\n{body}"
    return f"{len(items)} tenant(s) are overdue on rent:\n{body}"


def property_info(language: str, data: dict | None) -> str:
    if not data:
        if language == "hi":
            return "माफ़ कीजिए, यह प्रॉपर्टी नहीं मिली। क्या आप नाम की जांच कर सकते हैं?"
        if language == "hinglish":
            return "Sorry, ye property nahi mili. Naam check kar sakte hain?"
        return "Sorry, I couldn't find that property. Could you double-check the name?"

    tenant_line = ""
    if data["tenant"]:
        rent = money(data["current_rent"] or 0)
        end = _fmt_date(data["agreement_end"]) if data["agreement_end"] else "—"
        if language == "hi":
            tenant_line = f" वर्तमान टेनेंट {data['tenant']} है, रेंट {rent}/माह, एग्रीमेंट {end} तक।"
        elif language == "hinglish":
            tenant_line = f" Current tenant {data['tenant']} hai, rent {rent}/month, agreement {end} tak."
        else:
            tenant_line = f" Current tenant is {data['tenant']}, paying {rent}/month, agreement until {end}."
    else:
        tenant_line = (
            " कोई टेनेंट नहीं है।" if language == "hi"
            else " Koi tenant nahi hai." if language == "hinglish"
            else " There's no current tenant."
        )

    if language == "hi":
        return (
            f"{data['name']} ({data['type']}, {data['location']}) — स्टेटस: {data['status']}, "
            f"मासिक रेंट {money(data['monthly_rent'])}.{tenant_line}"
        )
    if language == "hinglish":
        return (
            f"{data['name']} ({data['type']}, {data['location']}) — Status: {data['status']}, "
            f"monthly rent {money(data['monthly_rent'])}.{tenant_line}"
        )
    return (
        f"{data['name']} ({data['type']}, {data['location']}) — status: {data['status']}, "
        f"monthly rent {money(data['monthly_rent'])}.{tenant_line}"
    )
