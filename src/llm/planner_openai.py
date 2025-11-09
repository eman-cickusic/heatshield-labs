import json
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


def llm_plan(
    day_summary: Dict, language: str = "English", user_prompt: Optional[str] = None
) -> List[str]:
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
        lines = [line.strip("- ") for line in text.split("\n") if line.strip()]
        return lines[:8]
    except Exception:
        return []


def llm_chat_response(summary: Dict, question: str, language: str = "English") -> str:
    if not OPENAI_API_KEY:
        return ""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        system = (
            "You are HeatShield Copilot, a bilingual climate safety assistant for school leaders."
            f" Answer in {language}. Use clear, empathetic language and cite concrete metrics"
            " from the provided summary (tiers, WBGT peaks, PM2.5, school name)."
            " If information is unavailable, say so and suggest the best next action."
        )
        prompt = (
            "School-day risk summary:\n"
            f"{json.dumps(summary, ensure_ascii=False)}\n"
            f"Question:\n{question.strip()}"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def llm_comm_kit(summary: Dict, language: str = "English") -> Dict[str, str]:
    if not OPENAI_API_KEY:
        return {}
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        system = (
            "Generate concise communication drafts for K-12 climate safety updates."
            " Return JSON with keys sms, email, pa. sms <=160 characters, email <=180 words,"
            " pa <=60 words in short sentences for announcements."
            f" Write entirely in {language}. Include hydration, rest, ventilation, mask guidance"
            " only if warranted by the summary."
        )
        prompt = json.dumps(summary, ensure_ascii=False)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        content = resp.choices[0].message.content.strip()
        try:
            parsed = json.loads(content)
            return {k: str(v).strip() for k, v in parsed.items()}
        except Exception:
            # Fallback: attempt to split by headings
            outputs: Dict[str, str] = {}
            sections = content.split("\n")
            current = None
            buffer: List[str] = []
            for line in sections:
                upper = line.strip().lower()
                if upper.startswith("sms"):
                    if current and buffer:
                        outputs[current] = "\n".join(buffer).strip()
                    current = "sms"
                    buffer = []
                elif upper.startswith("email"):
                    if current and buffer:
                        outputs[current] = "\n".join(buffer).strip()
                    current = "email"
                    buffer = []
                elif upper.startswith("pa"):
                    if current and buffer:
                        outputs[current] = "\n".join(buffer).strip()
                    current = "pa"
                    buffer = []
                else:
                    buffer.append(line)
            if current and buffer:
                outputs[current] = "\n".join(buffer).strip()
            return outputs
    except Exception:
        return {}


def llm_qa_feedback(issues: List[str], language: str = "English") -> str:
    if not OPENAI_API_KEY or not issues:
        return ""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=OPENAI_API_KEY)
        system = (
            "You are a data quality aide for school uploads."
            f" Respond in {language}. Provide a tight summary (<=80 words)"
            " highlighting the riskiest issues and suggesting fixes."
        )
        prompt = "Detected issues:\n" + "\n".join(f"- {issue}" for issue in issues)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""
