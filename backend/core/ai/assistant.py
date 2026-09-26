"""
AI assistant for the National Admin dashboard.

Design constraint from the spec: Gemini must explain the platform's own
calculations and must NEVER invent numerical values. We enforce this by
always building a `context` dict of real numbers from the database FIRST,
then instructing Gemini (via the system prompt) to only reason over those
numbers — never to compute or guess new ones. If GEMINI_API_KEY isn't set,
or the API call fails, `answer_question` falls back to a rule-based
responder that answers the same handful of question types directly from
the same context dict, so the assistant never just goes silent.
"""
import json
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent"

SYSTEM_INSTRUCTIONS = (
    "You are the AI assistant embedded in a national health supply-chain command center. "
    "You will be given a JSON `context` object containing real numbers already computed by the "
    "platform's backend (stock levels, forecasts, risk scores, redistribution recommendations). "
    "Answer the user's question using ONLY the numbers in `context`. "
    "Do not invent, estimate, or round in a way that changes any figure. "
    "If the context does not contain enough information to answer, say so plainly instead of guessing. "
    "Keep answers concise (3-6 sentences) and reference specific facility/medicine names and numbers from context."
)


def _build_context():
    """Real numbers only — this is what both Gemini and the fallback responder see."""
    from core.models import StockRisk, RedistributionRecommendation, Facility

    top_risks = list(
        StockRisk.objects.select_related("facility", "medicine")
        .filter(risk_level__in=["high", "critical"])
        .order_by("-risk_score")[:15]
        .values("facility__name", "medicine__name", "risk_level", "risk_score",
                 "days_of_stock", "shortage_quantity", "expected_stockout_date", "explanation")
    )
    top_redistributions = list(
        RedistributionRecommendation.objects.select_related("source_facility", "destination_facility", "medicine")
        .order_by("-computed_at")[:15]
        .values("source_facility__name", "destination_facility__name", "medicine__name",
                 "recommended_quantity", "urgency", "distance_km", "reason")
    )
    national_counts = {
        level: StockRisk.objects.filter(risk_level=level).count()
        for level in ["low", "medium", "high", "critical"]
    }
    return {
        "national_risk_counts": national_counts,
        "top_risks": top_risks,
        "top_redistribution_recommendations": top_redistributions,
        "total_facilities": Facility.objects.count(),
    }


def _call_gemini(question: str, context: dict) -> str | None:
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        return None
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTIONS}]},
        "contents": [{
            "role": "user",
            "parts": [{"text": f"context = {json.dumps(context, default=str)}\n\nQuestion: {question}"}],
        }],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400},
    }
    try:
        resp = requests.post(
            f"{GEMINI_ENDPOINT}?key={api_key}", json=payload, timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception:  # noqa: BLE001 - any failure -> fallback, never a 500 to the user
        logger.exception("Gemini API call failed, using rule-based fallback")
        return None


def _rule_based_fallback(question: str, context: dict) -> str:
    """
    Answers the spec's example question types directly from `context`
    without any external API. Used when GEMINI_API_KEY is unset or the
    call fails, so the assistant always responds with real numbers.
    """
    q = question.lower()
    counts = context["national_risk_counts"]
    top_risks = context["top_risks"]
    top_redis = context["top_redistribution_recommendations"]

    if not top_risks:
        return ("[Offline mode — rule-based fallback, Gemini API not configured] "
                "No high or critical risk facility/medicine pairs are currently on record. "
                f"National counts: {counts}.")

    if any(k in q for k in ["immediate attention", "urgent", "which medicines", "what needs"]):
        lines = [f"- {r['medicine__name']} at {r['facility__name']}: {r['risk_level']} risk "
                 f"(score {r['risk_score']}, ~{r['days_of_stock']} days of stock left)"
                 for r in top_risks[:5]]
        return ("[Offline mode — rule-based fallback] Medicines needing immediate attention:\n" + "\n".join(lines))

    if "why" in q and "risk" in q:
        r = top_risks[0]
        return f"[Offline mode — rule-based fallback] {r['facility__name']} / {r['medicine__name']}: {r['explanation']}"

    if "how much" in q and "order" in q:
        r = top_risks[0]
        return (f"[Offline mode — rule-based fallback] For {r['medicine__name']} at {r['facility__name']}, "
                f"the projected shortage is {r['shortage_quantity']} units over the forecast period — "
                f"that's the minimum recommended order quantity to close the gap.")

    if "redistribut" in q or "where can we" in q:
        if not top_redis:
            return "[Offline mode — rule-based fallback] No redistribution opportunities are currently recommended."
        r = top_redis[0]
        return (f"[Offline mode — rule-based fallback] {r['source_facility__name']} has transferable surplus of "
                f"{r['medicine__name']} and could send {r['recommended_quantity']} units to "
                f"{r['destination_facility__name']} ({r['distance_km']} km away, {r['urgency']} urgency). "
                f"Reason: {r['reason']}")

    if "priorit" in q or "emergency" in q:
        crit = [r for r in top_risks if r["risk_level"] == "critical"][:5]
        if not crit:
            return "[Offline mode — rule-based fallback] No critical-risk items right now; highest priority is the top of the high-risk list."
        lines = [f"- {r['medicine__name']} at {r['facility__name']} (score {r['risk_score']})" for r in crit]
        return "[Offline mode — rule-based fallback] Prioritize these critical items first:\n" + "\n".join(lines)

    return (f"[Offline mode — rule-based fallback, Gemini API not configured] "
            f"National risk snapshot: {counts}. Top concern: {top_risks[0]['medicine__name']} at "
            f"{top_risks[0]['facility__name']} ({top_risks[0]['risk_level']} risk). "
            f"Ask about specific medicines, facilities, redistribution, or emergency priorities for more detail.")


def answer_question(question: str) -> dict:
    context = _build_context()
    gemini_answer = _call_gemini(question, context)
    if gemini_answer:
        return {"answer": gemini_answer, "source": "gemini", "grounded_context_size": len(json.dumps(context, default=str))}
    return {"answer": _rule_based_fallback(question, context), "source": "fallback", "grounded_context_size": len(json.dumps(context, default=str))}

