from typing import Dict, List, Optional
from ..config import OPENAI_API_KEY

SAFETY_RAILS = [
    "No medical or legal advice; direct staff to district health partners when needed.",
    "Keep tone calm, practical, and equity-centered; avoid panic-inducing language.",
    "Recommend only actions a K-12 school can execute within the day (shade, hydration, staggered recess, HVAC checks, family comms).",
]


def _system_prompt(language: str) -> str:
    rails = "\n".join(f"- {rule}" for rule in SAFETY_RAILS)
    return (
        "You are HeatShield, a climate-adaptive school day planner."
        " You translate risk summaries into a concise, numbered plan for principals."
        f" Respond entirely in {language}, using the same language for headings and actions."
        " Format guidance as an ordered list (1., 2., ...) capped at 8 items."
        " Blend WBGT tiers and PM2.5 context."
        " Safety rails:\n"
        f"{rails}\n"
        "Always call out hydration, rest breaks, and indoor fallbacks when risks escalate."
    )


def llm_plan(day_summary: Dict, language: str = "English", user_prompt: Optional[str] = None) -> List[str]:
    if not OPENAI_API_KEY:
        return []
    try:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        extra = ""
        if user_prompt:
            extra = f"\nAdditional user guidance: {user_prompt.strip()}"
        content = f"Summary: {day_summary}{extra}"
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _system_prompt(language)},
                {"role": "user", "content": content},
            ],
            temperature=0.3,
        )
        text = resp.choices[0].message.content
        lines = [l.strip("- ") for l in text.split("\n") if l.strip()]
        return lines[:8]
    except Exception:
        return []
