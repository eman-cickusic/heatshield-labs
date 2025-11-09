import os
from datetime import timedelta
from io import BytesIO
from pathlib import Path
import textwrap

import pandas as pd
import pydeck as pdk
import requests
import streamlit as st

try:
    from fpdf import FPDF
    from fpdf.errors import FPDFException
    from fpdf.enums import XPos, YPos
except Exception:
    FPDF = None


@st.cache_data(show_spinner=False)
def _read_csv(uploaded_file):
    return pd.read_csv(uploaded_file)


API = os.getenv("HEATSHIELD_API", "http://localhost:8000").rstrip("/")
LANG_CHOICES = ["English", "Spanish", "French", "Portuguese", "Haitian Creole"]
RISK_TIMEOUT = int(os.getenv("HEATSHIELD_RISK_TIMEOUT", "1800"))

if "is_running" not in st.session_state:
    st.session_state["is_running"] = False
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = {}
if "comm_kit_cache" not in st.session_state:
    st.session_state["comm_kit_cache"] = {}

st.set_page_config(page_title="HeatShield", layout="wide")
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;600&display=swap');
    :root {
        --glass-bg: rgba(255, 255, 255, 0.08);
        --glass-border: rgba(255, 255, 255, 0.18);
        --apple-text: #f5f5f7;
        --apple-subtle: #a1a1a6;
        --accent: rgba(120, 181, 255, 0.9);
    }
    html, body, h1, h2, h3, h4, .stApp {
        font-family: "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        color: var(--apple-text);
        background: #050505;
    }
    div[data-testid="stAppViewContainer"] {
        background: radial-gradient(circle at 20% 20%, rgba(255,255,255,0.08), rgba(4,4,6,0.98)),
                    linear-gradient(145deg, #03050a, #0c111b);
    }
    div[data-testid="stSidebar"] {
        background: rgba(10,10,12,0.7);
        border-right: 1px solid rgba(255,255,255,0.05);
        backdrop-filter: blur(24px);
    }
    .glass-panel,
    .hero-panel,
    .dataframe-container {
        position: relative;
        background: rgba(8, 10, 16, 0.82);
        border-radius: 26px;
        padding: 2rem;
        margin-bottom: 1.6rem;
        border: 2px solid transparent;
        background-image:
            linear-gradient(150deg, rgba(100,130,255,0.12), rgba(5,8,14,0.85)),
            linear-gradient(120deg, rgba(255,255,255,0.35), rgba(120,181,255,0.45));
        background-clip: padding-box, border-box;
        box-shadow: 0 35px 70px rgba(0,0,0,0.55);
        backdrop-filter: blur(24px);
        transition: transform 0.35s ease, border 0.35s ease, box-shadow 0.35s ease;
        animation: fadeUp 0.6s ease both;
    }
    .glass-panel:hover {
        transform: translateY(-2px);
        border-color: rgba(255,255,255,0.35);
        box-shadow: 0 40px 80px rgba(0,0,0,0.65);
    }
    @keyframes fadeUp {
        from { opacity: 0; transform: translateY(12px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .hero-panel {
        margin-bottom: 2.6rem;
        text-align: center;
        padding: 2.8rem;
        background-image:
            linear-gradient(140deg, rgba(255,255,255,0.08), rgba(12,17,29,0.9)),
            linear-gradient(120deg, rgba(255,255,255,0.4), rgba(120,181,255,0.4));
    }
    .hero-eyebrow {
        letter-spacing: 0.3rem;
        text-transform: uppercase;
        color: var(--apple-subtle);
        font-size: 0.85rem;
        margin-bottom: 0.7rem;
    }
    .hero-headline {
        font-size: clamp(2.2rem, 5vw, 3.6rem);
        font-weight: 600;
        margin-bottom: 0.9rem;
    }
    .hero-panel p {
        color: var(--apple-subtle);
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .hero-cta {
        padding: 0.85rem 2.4rem;
        border-radius: 999px;
        background: rgba(255,255,255,0.18);
        border: 1px solid rgba(255,255,255,0.25);
        color: var(--apple-text);
        font-weight: 600;
        text-decoration: none;
        backdrop-filter: blur(12px);
        transition: box-shadow 0.3s ease, transform 0.3s ease, border 0.3s ease;
    }
    .hero-cta:hover {
        box-shadow: 0 18px 35px rgba(0,0,0,0.55);
        transform: translateY(-2px);
        border-color: rgba(255,255,255,0.45);
    }
    button,
    .stButton button,
    .stDownloadButton button {
        border-radius: 14px;
        min-height: 52px;
        transition: box-shadow 0.25s ease, transform 0.25s ease, border 0.25s ease;
        background: rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.12);
        color: var(--apple-text);
    }
    .stButton button:hover:not(:disabled),
    .stDownloadButton button:hover:not(:disabled) {
        box-shadow: 0 18px 35px rgba(0,0,0,0.55);
        transform: translateY(-1px);
        border-color: rgba(255,255,255,0.35);
    }
    .stButton button:focus-visible,
    .stDownloadButton button:focus-visible,
    .stRadio > div [role='radio']:focus-visible,
    .stSelectbox div[data-baseweb="select"] button:focus-visible,
    .stFileUploader button:focus-visible {
        outline: 3px solid var(--accent) !important;
        outline-offset: 3px;
    }
    .stFileUploader button[disabled] {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .stRadio > div [role='radio'] {
        padding: 0.45rem 0.65rem;
        border-radius: 12px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
    }
    .plan-card {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 1.2rem;
        margin-bottom: 1.2rem;
        background: rgba(7,10,17,0.78);
        backdrop-filter: blur(18px);
        box-shadow: 0 30px 60px rgba(0,0,0,0.5);
        transition: border-color 0.25s ease, box-shadow 0.25s ease, transform 0.25s ease;
    }
    .plan-card:hover {
        border-color: rgba(255,255,255,0.35);
        box-shadow: 0 35px 70px rgba(0,0,0,0.6);
        transform: translateY(-2px);
    }
    .legend-dot {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    .dataframe-container {
        padding: 1rem;
    }
    .stDataFrame {
        border-radius: 18px !important;
        overflow: hidden !important;
    }
    .stDataFrame div[data-testid="StyledTable"] {
        background: rgba(7,10,17,0.65);
    }
    div[data-testid="stAlert"] {
        border-radius: 18px;
        background: rgba(10,12,20,0.88);
        border: 1px solid rgba(255,255,255,0.15);
        color: var(--apple-text);
        box-shadow: 0 22px 55px rgba(0,0,0,0.55);
        backdrop-filter: blur(18px);
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span {
        color: var(--apple-text);
    }
    div[data-testid="stMetric"] {
        border-radius: 18px;
        padding: 0.9rem 1.1rem;
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.1);
    }
    div[data-testid="stMetricLabel"] {
        color: var(--apple-subtle);
    }
    .step-heading-panel {
        padding: 1.2rem 2rem;
        margin-bottom: 0.8rem;
    }
    .step-heading {
        font-size: 1.4rem;
        font-weight: 600;
        margin: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="hero-panel">
        <p class="hero-eyebrow">HeatShield · Labs</p>
        <div class="hero-headline">Plan tomorrow's school day with live climate resilience.</div>
        <p>Immersive glass UI, bilingual-ready action cards, and ERA5/OpenAQ provenance — all in one glance.</p>
        <a class="hero-cta" href="#step-1">Start planning</a>
    </section>
    """,
    unsafe_allow_html=True,
)


def _pdf_safe(text: str) -> str:
    return text.encode("latin-1", "replace").decode("latin-1")


def _pdf_wrapped_lines(text: str, width: int = 90):
    cleaned = _pdf_safe(text)
    for chunk in textwrap.wrap(cleaned, width=width, break_long_words=True, break_on_hyphens=False):
        yield chunk or " "


def _pdf_write_multiline(pdf: "FPDF", text: str, line_height: float = 6.0) -> None:
    width = max(pdf.w - pdf.l_margin - pdf.r_margin, 1.0)
    for chunk in _pdf_wrapped_lines(text):
        try:
            pdf.multi_cell(width, line_height, chunk, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        except FPDFException:
            for char in chunk:
                pdf.multi_cell(width, line_height, char, new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _step_heading(step_id: str, aria_label: str, title: str) -> None:
    st.markdown(
        f"""
        <section id="{step_id}" class="glass-panel step-heading-panel" role="region" aria-label="{aria_label}">
            <p class="step-heading">{title}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )


st.sidebar.title("Planner steps")
st.sidebar.markdown("[1 - Schools](#step-1)")
st.sidebar.markdown("[2 - Planner](#step-2)")
st.sidebar.markdown("[3 - Results](#step-3)")
st.sidebar.markdown("[4 - Map](#step-4)")

st.title("Plan tomorrow's school day with live heat and air-quality risks")
st.caption(
    "Demo runs instantly with synthetic weather. Live pulls ERA5/OpenAQ data and can take up to 30 minutes per school."
)

_step_heading("step-1", "School upload", "Step 1 - Upload schools")

with st.container():
    col_upload, col_help = st.columns([1.5, 1])
    with col_upload:
        uploader = st.file_uploader(
            "Schools CSV (name, lat, lon)",
            type=["csv"],
            help="Tap or click to select or drag a CSV file. Disabled while live request runs.",
            disabled=st.session_state["is_running"],
        )
        if uploader:
            try:
                schools_df = _read_csv(uploader)
            except Exception as exc:
                st.error(f"Could not read CSV: {exc}")
                st.stop()
        else:
            demo_path = Path(__file__).resolve().parents[1] / "data" / "schools_demo.csv"
            schools_df = pd.read_csv(demo_path)
            st.caption("Using bundled demo schools (data/schools_demo.csv).")

    required_cols = {"name", "lat", "lon"}
    if not required_cols.issubset(schools_df.columns):
        st.error("CSV must include columns: name, lat, lon.")
        st.stop()
    if not ((schools_df["lat"].between(-90, 90)) & (schools_df["lon"].between(-180, 180))).all():
        st.error("Latitude must be [-90,90] and longitude [-180,180].")

st.success(f"{len(schools_df)} schools loaded.", icon="✅")
st.dataframe(schools_df, use_container_width=True)

qa_feedback = None
qa_error = None
try:
    qa_payload = {"schools": schools_df[["name", "lat", "lon"]].to_dict(orient="records")}
    qa_resp = requests.post(f"{API}/qa/upload", json=qa_payload, timeout=25)
    if qa_resp.status_code == 200:
        qa_feedback = qa_resp.json()
    else:
        qa_error = f"status {qa_resp.status_code}"
except requests.exceptions.RequestException as exc:
    qa_error = str(exc)

qa_area = st.expander("AI QA review", expanded=bool(qa_feedback and qa_feedback.get("issue_count")))
with qa_area:
    if qa_feedback:
        issue_count = qa_feedback.get("issue_count", 0)
        score = qa_feedback.get("score", 0)
        if issue_count == 0:
            st.success(f"No blocking issues detected. QA score: {score}/100.", icon="✅")
        else:
            st.warning(
                f"{issue_count} potential issue(s) detected. QA score: {score}/100.",
                icon="⚠️",
            )
            for idx, issue in enumerate(qa_feedback.get("issues", []), start=1):
                severity = issue.get("severity", "info").title()
                st.write(f"{idx}. **{severity}** — {issue.get('message')}")
        if qa_feedback.get("llm"):
            st.caption(qa_feedback["llm"])
    elif qa_error:
        st.caption(f"AI QA temporarily unavailable ({qa_error}).")
    else:
        st.caption("QA results will appear once the API responds.")

    with col_help:
        st.info(
            "Tip: run a single school in Live mode first to prove connectivity. Demo mode is instant and great for judges.",
            icon="💡",
        )
        st.caption(
            "Keyboard: focus the uploader and press Enter/Space to open the file dialog; Esc cancels."
        )

_step_heading("step-2", "Planner controls", "Step 2 - Configure planner")

with st.container():
    with st.form("planner_form"):
        left_form, right_form = st.columns([1.4, 1])
        with left_form:
            today = pd.Timestamp.today().date()
            max_live_date = (pd.Timestamp.today() - pd.Timedelta(days=5)).date()
            min_calendar_date = pd.Timestamp(2020, 1, 1).date()
            date_value = st.date_input(
                "Target date",
                pd.Timestamp.today(),
                min_value=min_calendar_date,
                max_value=today,
            )
            selected_date = pd.Timestamp(date_value).date()
            date = selected_date.strftime("%Y-%m-%d")
            planner_mode = st.selectbox(
                "Planner",
                ["rule", "llm"],
                help="Rule mode is deterministic. LLM mode uses your OpenAI key to draft bilingual-ready actions.",
            )
            language = st.selectbox("Plan language", LANG_CHOICES, index=0)
            custom_prompt = st.text_area(
                "Optional LLM instructions",
                placeholder="Call out athletics, aftercare, bilingual robocalls…",
                max_chars=400,
            ).strip()
        with right_form:
            data_source = st.radio(
                "Data source",
                ["Demo (synthetic)", "Live ERA5/OpenAQ"],
                index=0,
                help="Demo uses synthetic weather; Live pulls ASDI ERA5 + OpenAQ and may take 30–40 min per school.",
            )
            use_demo = data_source != "Live ERA5/OpenAQ"
            st.caption(
                f"{len(schools_df)} schools queued - "
                + ("Demo runs instantly." if use_demo else "Live queues each school sequentially.")
            )
            if not use_demo:
                st.warning("Expect long runtimes. Try one campus first, then expand.", icon="⏳")
        submitted = st.form_submit_button(
            "Generate today's safety plan",
            use_container_width=True,
            disabled=st.session_state["is_running"],
        )

results = []
units = {}
error_message = None

# Reserve placeholders so layout shift is minimized before results arrive
placeholder_cards = st.empty()
map_rows = []

if submitted:
    if not use_demo and selected_date > max_live_date:
        st.error(
            f"Live ERA5 data currently stops at {max_live_date}. Choose an earlier date or switch to Demo.",
        )
    else:
        st.session_state["is_running"] = True
        payload = {
            "schools": schools_df.to_dict(orient="records"),
            "date": date,
            "use_demo": use_demo,
        }
        with st.spinner(
            "Fetching ERA5/OpenAQ data…" if not use_demo else "Generating deterministic plan…"
        ):
            try:
                risk_resp = requests.post(f"{API}/risk", json=payload, timeout=RISK_TIMEOUT)
                risk_resp.raise_for_status()
                response_json = risk_resp.json()
                units = response_json.get("units", {})
                results = response_json.get("results", [])
            except requests.exceptions.ReadTimeout:
                error_message = (
                    "Live data pull exceeded the timeout. Try fewer schools or stay in Demo."
                )
            except requests.exceptions.RequestException as exc:
                error_message = f"Risk request failed: {exc}"
            finally:
                st.session_state["is_running"] = False

if error_message:
    st.error(error_message)
    if st.button("Retry request", type="secondary"):
        st.experimental_rerun()

if st.session_state["is_running"] and not results and not error_message:
    with placeholder_cards.container():
        st.info("Waiting for results. Keep this tab open while Live mode completes.")
        sample_count = min(len(schools_df), 3)
        for idx in range(sample_count):
            with st.container():
                st.markdown(f"#### Loading plan… (school {idx + 1})")
                progress = st.progress(0.2)
                st.caption("Fetching ERA5/OpenAQ data for this school.")
                st.empty()

_step_heading("step-3", "Results and plans", "Step 3 - Review summaries & plans")

school_entries: list[dict] = []
with st.container():
    if results:
        for idx, item in enumerate(results):
            school = item["school"]
            summary = item.get("summary", {})
            sources = item.get("sources", {})
            tiers = summary.get("hours_by_tier", {})
            entry_label = f"{school['name']} (#{idx + 1})"
            school_entries.append({"label": entry_label, "summary": summary, "school": school})
            card = st.container()
            with card:
                st.markdown("<div class='plan-card'>", unsafe_allow_html=True)
                st.markdown(f"#### {school['name']}")
                metrics = st.columns(3)
                metrics[0].metric("Peak WBGT (°C)", f"{summary.get('peak_wbgt_c', 0):.1f}")
                metrics[1].metric(
                    "Red + orange hours", tiers.get("red", 0) + tiers.get("orange", 0)
                )
                metrics[2].metric("Source", sources.get("met_source", "demo"))

                with st.expander("See raw summary data"):
                    st.json(summary)

                plan_payload = {
                    "risk_report": summary,
                    "mode": planner_mode,
                    "language": language,
                    "user_prompt": custom_prompt or None,
                }
                plan_actions: list[str] = []
                try:
                    plan_resp = requests.post(f"{API}/plan", json=plan_payload, timeout=120)
                    plan_resp.raise_for_status()
                    plan_actions = plan_resp.json().get("actions", [])
                except requests.exceptions.RequestException as exc:
                    st.error(f"Planner request failed: {exc}")

                st.markdown("**Plan**")
                if plan_actions:
                    for action in plan_actions:
                        st.write(f"- {action}")
                else:
                    if st.session_state["is_running"]:
                        st.caption("Awaiting planner response…")
                    else:
                        st.info("No actions returned. Try rule mode or verify summary data.")

                try:
                    explain_resp = requests.post(
                        f"{API}/explain", json={"summary": summary}, timeout=30
                    )
                    if explain_resp.status_code == 200:
                        st.caption(explain_resp.json().get("text", ""))
                except requests.exceptions.RequestException:
                    st.caption("Explain service unavailable.")

                kit_cache = st.session_state["comm_kit_cache"]
                kit_key = f"{school['name']}|{date}"
                with st.expander("Communications kit", expanded=False):
                    cached_kit = kit_cache.get(kit_key)
                    if not cached_kit:
                        if st.button(f"Draft comms for {school['name']}", key=f"kit-btn-{kit_key}"):
                            with st.spinner("Drafting communications kit..."):
                                try:
                                    kit_resp = requests.post(
                                        f"{API}/communications",
                                        json={
                                            "summary": summary,
                                            "school_name": school["name"],
                                            "language": language,
                                        },
                                        timeout=90,
                                    )
                                    kit_resp.raise_for_status()
                                    cached_kit = kit_resp.json()
                                    kit_cache[kit_key] = cached_kit
                                except requests.exceptions.RequestException as exc:
                                    st.error(f"Could not generate communications kit: {exc}")
                    if cached_kit:
                        channels = cached_kit.get("channels", {})
                        for channel, label in [
                            ("sms", "SMS / text blast"),
                            ("email", "Email newsletter"),
                            ("pa", "PA / morning announcement"),
                        ]:
                            content = channels.get(channel)
                            if content:
                                st.text_area(
                                    label,
                                    value=content,
                                    height=80 if channel != "email" else 160,
                                    key=f"{kit_key}-{channel}",
                                    disabled=True,
                                )
                        st.caption(f"Source: {cached_kit.get('source', 'template')}")

                if FPDF and plan_actions:
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Helvetica", size=14)
                    pdf.cell(
                        0,
                        10,
                        _pdf_safe(f"HeatShield Plan - {school['name']} ({date})"),
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                    )
                    pdf.set_font("Helvetica", size=11)
                    pdf.cell(0, 8, _pdf_safe("Summary:"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    for tier_name in ["green", "yellow", "orange", "red"]:
                        pdf.cell(
                            0,
                            6,
                            _pdf_safe(f"  {tier_name}: {tiers.get(tier_name, 0)}h"),
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                        )
                    peak = summary.get("peak_wbgt_c")
                    if peak is not None:
                        pdf.cell(
                            0,
                            6,
                            _pdf_safe(f"  Peak WBGT: {peak:.1f} {units.get('wbgt_c', '°C')}"),
                            new_x=XPos.LMARGIN,
                            new_y=YPos.NEXT,
                        )
                    pdf.cell(0, 8, _pdf_safe("Actions:"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                    for i, action in enumerate(plan_actions, 1):
                        _pdf_write_multiline(pdf, f"{i}. {action}")
                    raw_pdf = pdf.output(dest="S")
                    buffer = BytesIO(
                        bytes(raw_pdf)
                        if isinstance(raw_pdf, bytearray)
                        else raw_pdf.encode("latin-1")
                    )
                    download_clicked = st.download_button(
                        label=f"Download plan for {school['name']}",
                        data=buffer,
                        file_name=f"HeatShield_{school['name'].replace(' ', '_')}_{date}.pdf",
                        mime="application/pdf",
                    )
                    if download_clicked:
                        st.toast(f"Plan for {school['name']} downloaded.")
                st.markdown("</div>", unsafe_allow_html=True)

    else:
        with placeholder_cards:
            st.info(
                'No plans yet. Configure the planner and click "Generate today\'s safety plan".'
            )

if school_entries:
    st.markdown(
        "<section class='glass-panel' role='region' aria-label='AI copilot'>",
        unsafe_allow_html=True,
    )
    st.subheader("HeatShield Copilot")
    st.caption("Ask natural-language questions about any school plan.")
    labels = [entry["label"] for entry in school_entries]
    selected_label = st.selectbox("Focus on", labels, key="assistant-select")
    selected_entry = next(entry for entry in school_entries if entry["label"] == selected_label)
    chat_key = f"{selected_label}|{date}"
    history = st.session_state["assistant_history"].setdefault(chat_key, [])
    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    user_prompt = st.chat_input("Ask the HeatShield Copilot")
    if user_prompt:
        history.append({"role": "user", "content": user_prompt})
        with st.chat_message("user"):
            st.markdown(user_prompt)
        with st.chat_message("assistant"):
            with st.spinner("Gathering insights..."):
                reply_text = ""
                try:
                    assist_resp = requests.post(
                        f"{API}/assistant",
                        json={
                            "summary": selected_entry["summary"],
                            "question": user_prompt,
                            "language": language,
                        },
                        timeout=90,
                    )
                    assist_resp.raise_for_status()
                    reply_text = assist_resp.json().get("text", "")
                except requests.exceptions.RequestException as exc:
                    reply_text = f"Assistant unavailable: {exc}"
                st.markdown(reply_text or "No response available.")
        history.append({"role": "assistant", "content": reply_text or "No response available."})
    st.markdown("</section>", unsafe_allow_html=True)

_step_heading("step-4", "Map of tiers", "Step 4 - Map of worst daily tiers")

with st.container():
    placeholder_map = st.empty()
    map_rows = []
    for item in results:
        tiers = item.get("summary", {}).get("hours_by_tier", {})
        worst = next(
            (t for t in ["red", "orange", "yellow", "green"] if tiers.get(t, 0) > 0), "green"
        )
        map_rows.append(
            {
                "name": item["school"]["name"],
                "lat": item["school"]["lat"],
                "lon": item["school"]["lon"],
                "tier": worst,
            }
        )

    with placeholder_map.container():
        if map_rows:
            dfm = pd.DataFrame(map_rows)
            colors = {
                "green": [34, 139, 34],
                "yellow": [255, 215, 0],
                "orange": [255, 140, 0],
                "red": [220, 20, 60],
            }
            dfm["color"] = dfm["tier"].map(colors)
            midpoint = [float(dfm["lat"].mean()), float(dfm["lon"].mean())]
            layer = pdk.Layer(
                "ScatterplotLayer",
                data=dfm,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_line_color=[0, 0, 0],
                radius_min_pixels=6,
                radius_max_pixels=30,
                get_radius=20000,
                pickable=True,
            )
            view_state = pdk.ViewState(latitude=midpoint[0], longitude=midpoint[1], zoom=4)
            try:
                st.pydeck_chart(
                    pdk.Deck(
                        layers=[layer],
                        initial_view_state=view_state,
                        tooltip={"text": "{name}\nWorst tier: {tier}"},
                        height=420,
                    )
                )
            except Exception as exc:
                st.warning(
                    f"Map failed to render: {exc}. Refer to the textual summary below.", icon="⚠️"
                )
            legend_cols = st.columns(4)
            for idx, tier in enumerate(["green", "yellow", "orange", "red"]):
                legend_cols[idx].markdown(
                    f"<div style='display:flex;align-items:center;font-size:0.85rem;'>"
                    f"<span style='width:16px;height:16px;background-color:rgb{tuple(colors[tier])};"
                    f"display:inline-block;margin-right:6px;border-radius:50%;'></span>{tier.title()}</div>",
                    unsafe_allow_html=True,
                )
            tier_counts = dfm["tier"].value_counts()
            summary_text = ", ".join(f"{tier}:{count}" for tier, count in tier_counts.items())
            st.caption(
                f"{len(map_rows)} schools plotted. Tier distribution – {summary_text}. "
                "Alt description: each marker is a school colored by its worst WBGT tier."
            )
        else:
            st.info("Generate a plan to populate the map.")
