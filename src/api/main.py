import logging
from collections import Counter
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Optional

from ..data.era5 import fetch_era5_hourly
from ..data.openaq import fetch_pm25, fetch_pm25_s3
from ..llm.planner_openai import (
    llm_plan,
    llm_chat_response,
    llm_comm_kit,
    llm_qa_feedback,
)
from ..ml.planner_rule_based import plan_from_summary
from ..ml.risk import compute_risk, summarize_day
from ..ml.wbgt import _wbgt_thresholds_from_env

app = FastAPI(title="HeatShield API", version="0.1.0")
LOGGER = logging.getLogger(__name__)


class School(BaseModel):
    name: str
    lat: float
    lon: float


class RiskRequest(BaseModel):
    schools: List[School]
    date: str = Field(..., description="YYYY-MM-DD")
    use_demo: bool = False


class PlanRequest(BaseModel):
    risk_report: dict
    mode: str = Field("rule", description="rule|llm")
    language: str = Field("English", description="Language for textual plan output.")
    user_prompt: Optional[str] = Field(
        default=None, description="Optional context appended to the base LLM prompt."
    )


class ExplainRequest(BaseModel):
    summary: dict


class AssistantRequest(BaseModel):
    summary: dict
    question: str
    language: str = "English"


class CommunicationsRequest(BaseModel):
    summary: dict
    school_name: Optional[str] = None
    language: str = "English"


class QARequest(BaseModel):
    schools: List[School]


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/risk")
async def risk(req: RiskRequest):
    outputs = []
    for s in req.schools:
        met = fetch_era5_hourly(s.lat, s.lon, req.date, req.use_demo)
        pm = fetch_pm25_s3(s.lat, s.lon, req.date)
        aq_source = "none"
        if not pm.empty:
            aq_source = getattr(pm, "attrs", {}).get("aq_source", "openaq-s3")
        else:
            LOGGER.info(
                "OpenAQ S3 empty near lat=%.3f lon=%.3f on %s; attempting REST fallback.",
                s.lat,
                s.lon,
                req.date,
            )
            pm = fetch_pm25(s.lat, s.lon, req.date)
            if not pm.empty:
                aq_source = "openaq-rest"
                LOGGER.info("OpenAQ REST fallback succeeded near lat=%.3f lon=%.3f.", s.lat, s.lon)
            else:
                LOGGER.warning(
                    "OpenAQ REST fallback also empty near lat=%.3f lon=%.3f on %s.",
                    s.lat,
                    s.lon,
                    req.date,
                )
        if not pm.empty:
            met = met.merge(pm, on="time", how="left")
            met["pm25"] = met["pm25"].interpolate().fillna(method="bfill").fillna(method="ffill")
        df = compute_risk(met)
        summary = summarize_day(df)
        met_source = getattr(met, "attrs", {}).get(
            "met_source", ("demo" if req.use_demo else "asdi-era5")
        )
        outputs.append(
            {
                "school": s.model_dump(),
                "summary": summary,
                "sources": {"met_source": met_source, "aq_source": aq_source},
            }
        )
    units = {
        "temp_c": "°C",
        "wbgt_c": "°C",
        "pm25": "µg/m³",
        "rh": "0-1",
        "wind_ms": "m/s",
        "swdown": "W/m²",
    }
    return {"date": req.date, "results": outputs, "units": units}


@app.post("/plan")
async def plan(req: PlanRequest):
    actions = plan_from_summary(req.risk_report)
    if req.mode == "llm":
        llm_actions = llm_plan(
            req.risk_report,
            language=req.language,
            user_prompt=req.user_prompt,
        )
        if llm_actions:
            actions = llm_actions
    return {"actions": actions, "mode": req.mode, "language": req.language}


def _explain_text(summary: dict) -> str:
    hours = summary.get("hours_by_tier", {}) or {}
    peak = summary.get("peak_wbgt_c")
    t1, t2, t3 = _wbgt_thresholds_from_env()
    ordered = [
        ("red", t3, 1000),
        ("orange", t2, t3),
        ("yellow", t1, t2),
        ("green", -100, t1),
    ]
    worst = next((tier for tier, _, _ in ordered if hours.get(tier, 0) > 0), "green")
    parts = []
    parts.append(
        f"WBGT thresholds set at {t1:.1f}/{t2:.1f}/{t3:.1f} degC (green/yellow/orange/red)."
    )
    parts.append(
        "Reported hours by tier: "
        + ", ".join([f"{k}={hours.get(k,0)}" for k in ["green", "yellow", "orange", "red"]])
        + "."
    )
    if peak is not None:
        parts.append(
            f"Peak WBGT reached {peak:.1f} degC, driving {worst} guidance during hotter periods."
        )
    else:
        parts.append(f"Peak WBGT unavailable; guidance based on tier distribution (worst={worst}).")
    parts.append(
        "The final plan is aligned to the worst daily tier to ensure safety and operational simplicity."
    )
    return " ".join(parts)


@app.post("/explain")
async def explain(req: ExplainRequest):
    text = _explain_text(req.summary)
    return {"text": text}


@app.post("/assistant")
async def assistant(req: AssistantRequest):
    ai_text = llm_chat_response(req.summary, req.question, req.language)
    if ai_text:
        return {"text": ai_text, "source": "llm"}
    fallback = _explain_text(req.summary)
    return {
        "text": "LLM assistant unavailable. Latest summary instead:\n" + fallback,
        "source": "fallback",
    }


@app.post("/communications")
async def communications(req: CommunicationsRequest):
    payload = llm_comm_kit(req.summary, req.language)
    if payload:
        return {"channels": payload, "source": "llm"}
    default = _explain_text(req.summary)
    sms = f"{req.school_name or 'This campus'} will follow heat safeguards today. Keep hydration, shade, and rest cycles active."
    email = (
        f"{req.school_name or 'Campus'} plan:\n{default}\n\n"
        "Actions: keep water stations stocked, rotate outdoor blocks <15 minutes, notify families if afternoon athletics move indoors."
    )
    pa = "Reminder: heat plan is in effect. Rotate groups indoors, log hydration breaks, alert the office if anyone feels ill."
    return {
        "channels": {"sms": sms, "email": email, "pa": pa},
        "source": "template",
    }


def _analyze_schools(schools: List[School]) -> dict:
    issues = []
    coord_map = {}
    for idx, school in enumerate(schools):
        row = school.model_dump()
        name = row.get("name", "").strip() or f"Row {idx + 1}"
        lat = row.get("lat")
        lon = row.get("lon")
        if lat is None or lon is None:
            issues.append({"severity": "high", "message": f"{name} missing latitude/longitude."})
            continue
        if not (-90 <= lat <= 90):
            issues.append({"severity": "high", "message": f"{name} latitude {lat} outside [-90, 90]."})
        if not (-180 <= lon <= 180):
            issues.append({"severity": "high", "message": f"{name} longitude {lon} outside [-180, 180]."})
        key = (round(lat, 3), round(lon, 3))
        coord_map.setdefault(key, []).append(name)
    name_counts = Counter(s.name.strip() for s in schools if s.name.strip())
    for school_name, count in name_counts.items():
        if count > 1:
            issues.append(
                {
                    "severity": "medium",
                    "message": f"School '{school_name}' appears {count} times. Confirm duplicates are intended.",
                }
            )
    for coord, items in coord_map.items():
        if len(items) > 1:
            sample = ", ".join(items[:5])
            issues.append(
                {
                    "severity": "medium",
                    "message": f"{len(items)} schools share coordinates {coord}: {sample}",
                }
            )
    if len(schools) > 200:
        issues.append(
            {
                "severity": "low",
                "message": f"Large upload ({len(schools)} schools). Consider demo/testing in smaller batches for Live mode.",
            }
        )
    score = max(0, 100 - len(issues) * 8)
    return {"issues": issues, "score": score}


@app.post("/qa/upload")
async def qa_upload(req: QARequest):
    analysis = _analyze_schools(req.schools)
    llm_notes = llm_qa_feedback([issue["message"] for issue in analysis["issues"]])
    return {
        **analysis,
        "issue_count": len(analysis["issues"]),
        "llm": llm_notes,
    }
