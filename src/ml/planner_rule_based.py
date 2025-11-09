from typing import List, Dict

# Deterministic, explainable planner mapping risk tiers to actions.

BASE_ACTIONS = {
    "green": ["Proceed as scheduled. Emphasize hydration and shade for outdoor time."],
    "yellow": [
        "Move PE to early periods or indoor shaded spaces.",
        "Increase water breaks (every 20 minutes).",
        "Use classrooms on lower floors if available."
    ],
    "orange": [
        "Cancel strenuous outdoor activities; switch to low-exertion indoor alternatives.",
        "Shorten recess; provide shaded/indoor options.",
        "Activate HEPA/portable filters if PM2.5 > 35."
    ],
    "red": [
        "Suspend outdoor activities; move assemblies online or staggered indoors.",
        "Masks recommended if PM2.5 > 55; prioritize rooms with best ventilation.",
        "Notify families of heat/smoke precautions."
    ]
}


def plan_from_summary(day_summary: Dict) -> List[str]:
    tiers = day_summary.get("hours_by_tier", {})
    actions = []
    # escalate to worst daily tier
    priority = ["red", "orange", "yellow", "green"]
    for t in priority:
        if t in tiers:
            actions += BASE_ACTIONS[t]
            break
    # always include universal steps
    actions += [
        "Ensure access to cool water and shaded rest areas.",
        "Post a simple schedule update on the staff WhatsApp or SMS.",
    ]
    return actions
