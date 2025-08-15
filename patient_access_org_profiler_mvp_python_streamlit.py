# patient_access_org_profiler_mvp_python_streamlit.py
# "No-API rollback" — CMS + Google News only, with robust loading and matching

import streamlit as st
import pandas as pd
import requests, io, os, time, difflib, json
import xml.etree.ElementTree as ET
from datetime import datetime

st.set_page_config(page_title="Patient Access Org Profiler — No API Keys", layout="wide")

# ---------------------------------------------------------------------
# Built-in tiny CMS sample (safety net so the app always shows something)
#   Columns mirror CMS "Hospital General Information" dataset.
# ---------------------------------------------------------------------
SAMPLE_CMS_CSV = """Hospital Name,Address,City,State,ZIP Code,County Name,Phone Number,Hospital Type,Hospital Ownership,Emergency Services,Hospital overall rating
UCSF Medical Center,505 Parnassus Ave,San Francisco,CA,94143,San Francisco,(415) 476-1000,Acute Care Hospitals,Voluntary non-profit - Private,Yes,5
Ochsner Medical Center,1514 Jefferson Hwy,New Orleans,LA,70121,Jefferson,(504) 842-3000,Acute Care Hospitals,Voluntary non-profit - Other,Yes,4
Kaiser Foundation Hospital - San Francisco,2425 Geary Blvd,San Francisco,CA,94115,San Francisco,(415) 833-2000,Acute Care Hospitals,Voluntary non-profit - Other,Yes,4
Massachusetts General Hospital,55 Fruit St,Boston,MA,02114,Suffolk,(617) 726-2000,Acute Care Hospitals,Voluntary non-profit - Private,Yes,5
Cleveland Clinic Main Campus,9500 Euclid Ave,Cleveland,OH,44195,Cuyahoga,(216) 444-2200,Acute Care Hospitals,Voluntary non-profit - Private,Yes,5
Mayo Clinic Hospital - Rochester,1216 2nd St SW,Rochester,MN,55902,Olmsted,(507) 284-2511,Acute Care Hospitals,Voluntary non-profit - Private,Yes,5
NYU Langone Health - Tisch Hospital,550 1st Ave,New York,NY,10016,New York,(212) 263-7300,Acute Care Hospitals,Voluntary non-profit - Private,Yes,5
Houston Methodist Hospital,6565 Fannin St,Houston,TX,77030,Harris,(713) 790-3311,Acute Care Hospitals,Voluntary non-profit - Private,Yes,5
"""

MEDICARE_URL = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
LOCAL_BACKUP = "cms_hospitals_backup.csv"  # optional: drop a full CMS export here

# ---------------------------------------------------------------------
# Data loading (resilient)
# ---------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_cms_data():
    # 1) Try Medicare URL with simple retries
    for attempt in range(3):
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(MEDICARE_URL, headers=headers, timeout=15)
            if resp.status_code == 200 and resp.content:
                df = pd.read_csv(io.BytesIO(resp.content), dtype=str)
                return df, f"Loaded CMS from Medicare (attempt {attempt+1})"
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            time.sleep(1.5 * (attempt + 1))

    # 2) Try local backup if present
    if os.path.exists(LOCAL_BACKUP):
        for enc in ["utf-8", "latin1", "utf-16"]:
            try:
                df = pd.read_csv(LOCAL_BACKUP, dtype=str, encoding=enc)
                return df, f"Loaded CMS from local backup ({enc})"
            except Exception:
                continue

    # 3) Fall back to small built-in sample
    df = pd.read_csv(io.StringIO(SAMPLE_CMS_CSV), dtype=str)
    return df, "Loaded CMS from built-in sample (fallback)"

# ---------------------------------------------------------------------
# News via Google News RSS (no API)
# ---------------------------------------------------------------------
def get_news(org_name, max_items=6):
    try:
        rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ', '+')}"
        r = requests.get(rss_url, timeout=12)
        articles = []
        if r.status_code == 200 and r.content:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:max_items]:
                title = (item.find("title").text or "").strip()
                link = (item.find("link").text or "").strip()
                pub_date = (item.find("pubDate").text or "").strip()
                articles.append({"title": title, "link": link, "date": pub_date})
        return articles
    except Exception:
        return []

# ---------------------------------------------------------------------
# Simple risk / opportunity heuristics from CMS fields
# ---------------------------------------------------------------------
def assess_risks_ops(row: dict):
    risks, ops = [], []
    rating = (row.get("Hospital overall rating") or "").strip()
    if rating.isdigit():
        r = int(rating)
        if r <= 2:
            risks.append("Low CMS star rating — perception/quality risk.")
        if r >= 4:
            ops.append("High CMS star rating — leverage reputation in access messaging.")
    if (row.get("Emergency Services") or "").strip().lower() == "no":
        risks.append("No emergency services — may affect inbound volumes and referral patterns.")
    owner = (row.get("Hospital Ownership") or row.get("Hospital ownership") or "").lower()
    if "government" in owner:
        ops.append("Government-owned — potential access to grants/public funding.")
    return risks, ops

# ---------------------------------------------------------------------
# Matching helpers (no extra deps)
# ---------------------------------------------------------------------
def format_label(r):
    return f"{r.get('Hospital Name','?')} — {r.get('City','?')}, {r.get('State','?')}"

def find_candidates(df: pd.DataFrame, query: str, limit=12):
    # Primary filter: substring match (case-insensitive)
    name_col = "Hospital Name" if "Hospital Name" in df.columns else None
    if not name_col:
        # Try common alternates
        for c in ["Facility Name", "Provider Name", "Organization Name", "Name"]:
            if c in df.columns:
                name_col = c
                break
    if not name_col:
        return pd.DataFrame(), None

    mask = df[name_col].str.contains(query, case=False, na=False)
    subset = df[mask].copy()

    # If too many or none, use difflib to get close matches
    if subset.empty:
        choices = df[name_col].dropna().astype(str).unique().tolist()
        close = difflib.get_close_matches(query, choices, n=limit, cutoff=0.6)
        subset = df[df[name_col].isin(close)].copy()

    return subset, name_col

# ---------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------
st.title("🏥 Patient Access Org Profiler — No API Keys")

with st.spinner("Loading CMS data..."):
    df_cms, load_msg = load_cms_data()

st.success(f"{load_msg}. Rows: {len(df_cms)}")

org = st.text_input("Enter a hospital/health system name (e.g., 'UCSF', 'Ochsner', 'Kaiser San Francisco'):")

if org:
    with st.spinner("Searching CMS..."):
        candidates, name_col = find_candidates(df_cms, org, limit=15)

    if name_col is None or candidates.empty:
        st.error("No matches found in CMS data. Try a different spelling or broader name.")
    else:
        # Let the user pick if multiple
        options = [(format_label(r), i) for i, r in candidates.iterrows()]
        label_to_index = {lbl: idx for lbl, idx in options}
        default_label = options[0][0]
        choice = st.selectbox("Pick a facility:", [lbl for lbl, _ in options], index=0)
        row = candidates.loc[label_to_index[choice]].to_dict()

        st.subheader("🏥 Facility Information")
        colA, colB = st.columns(2)
        with colA:
            st.write(f"**Hospital Name:** {row.get('Hospital Name') or row.get(name_col)}")
            st.write(f"**Address:** {row.get('Address','N/A')}")
            st.write(f"**City/State/ZIP:** {row.get('City','N/A')}, {row.get('State','N/A')} {row.get('ZIP Code','')}")
            st.write(f"**County:** {row.get('County Name','N/A')}")
            st.write(f"**Phone:** {row.get('Phone Number','N/A')}")
        with colB:
            st.write(f"**Hospital Type:** {row.get('Hospital Type','N/A')}")
            st.write(f"**Ownership:** {row.get('Hospital ownership') or row.get('Hospital Ownership','N/A')}")
            st.write(f"**Emergency Services:** {row.get('Emergency Services','N/A')}")
            st.write(f"**CMS Overall Rating:** {row.get('Hospital overall rating','N/A')}")

        st.subheader("📰 Recent News (Google News RSS)")
        news_items = get_news(row.get('Hospital Name') or row.get(name_col) or org)
        if news_items:
            for a in news_items:
                st.markdown(f"- [{a['title']}]({a['link']})  \n  <small>{a['date']}</small>", unsafe_allow_html=True)
        else:
            st.info("No recent news found via Google News RSS.")

        st.subheader("⚠️ Risks & 💡 Opportunities")
        risks, ops = assess_risks_ops(row)
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Risks**")
            if risks:
                for r in risks: st.write(f"- {r}")
            else:
                st.write("- None flagged from CMS fields.")
        with col2:
            st.markdown("**Opportunities**")
            if ops:
                for o in ops: st.write(f"- {o}")
            else:
                st.write("- None flagged from CMS fields.")

        # Download JSON dossier
        dossier = {
            "facility_info": row,
            "news": news_items,
            "risks": risks,
            "opportunities": ops,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source_notes": {
                "cms": load_msg,
                "news": "Google News RSS (no API)"
            },
        }
        st.download_button(
            label="📥 Download JSON Dossier",
            data=json.dumps(dossier, indent=2),
            file_name=f"{(row.get('Hospital Name') or row.get(name_col) or org).replace(' ','_')}_profile.json",
            mime="application/json"
        )

st.caption(
    "Data sources: CMS Hospital General Information & Google News RSS. "
    "This rollback intentionally avoids extra APIs and heavy scraping to keep reliability high."
)
