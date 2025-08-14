import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from rapidfuzz import process, fuzz

# ---- Load CMS Hospital Data ----
@st.cache_data
def load_cms_data():
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    try:
        df = pd.read_csv(url, dtype=str)
        return df
    except Exception:
        try:
            df_backup = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
            return df_backup
        except Exception:
            return pd.DataFrame()  # fallback empty

# ---- Fuzzy hospital matching ----
def match_hospital(name, df, threshold=70):
    if df.empty:
        return None
    choices = df["Hospital Name"].dropna().tolist()
    match, score, idx = process.extractOne(name, choices, scorer=fuzz.WRatio, score_cutoff=threshold)
    if match:
        return df.iloc[idx].to_dict()
    return None

# ---- Get News from Google News RSS ----
def get_news(org_name):
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ', '+')}"
    articles = []
    try:
        r = requests.get(rss_url, timeout=5)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:5]:
                articles.append({
                    "title": item.find("title").text,
                    "link": item.find("link").text,
                    "date": item.find("pubDate").text
                })
    except Exception:
        pass
    return articles

# ---- Risk/Opportunity Assessment (Hospitals Only) ----
def assess_risks_ops(row):
    risks, ops = [], []
    if row:
        if row.get("Hospital overall rating") and row["Hospital overall rating"].isdigit():
            rating = int(row["Hospital overall rating"])
            if rating <= 2:
                risks.append("Low star rating — potential quality/perception issues.")
            elif rating >= 4:
                ops.append("High star rating — leverage strong reputation.")
        if row.get("Emergency Services") == "No":
            risks.append("No emergency services — may affect patient volume mix.")
        if "Government" in (row.get("Hospital ownership") or ""):
            ops.append("Government-owned — may have grant or public funding access.")
    return risks, ops

# ---- Streamlit UI ----
st.title("🏥 Patient & Vendor Org Profiler")
st.write("Enter any organization or vendor name to generate a pre-discovery profile using only public data.")

org_name = st.text_input("Organization or Vendor Name")
df_cms = load_cms_data()

if org_name:
    # Try hospital match first
    hospital_info = match_hospital(org_name, df_cms)
    if hospital_info:
        st.success(f"Matched hospital: {hospital_info['Hospital Name']}")
        risks, ops = assess_risks_ops(hospital_info)
    else:
        st.info("No hospital match found. Treating as vendor or non-hospital organization.")
        hospital_info = None
        risks, ops = [], []

    # ---- Org Info ----
    st.subheader("🏢 Organization Information")
    st.json(hospital_info if hospital_info else {"Name": org_name})

    # ---- News ----
    st.subheader("📰 Recent News")
    news_items = get_news(org_name)
    if news_items:
        for article in news_items:
            st.markdown(f"- [{article['title']}]({article['link']}) ({article['date']})")
    else:
        st.write("No recent news found.")

    # ---- Risks & Opportunities ----
    if risks or ops:
        st.subheader("⚠️ Risks & 💡 Opportunities")
        if risks:
            st.markdown("**Risks:**")
            for r in risks: st.write(f"- {r}")
        if ops:
            st.markdown("**Opportunities:**")
            for o in ops: st.write(f"- {o}")

    # ---- Download JSON ----
    dossier = {
        "organization": org_name,
        "hospital_info": hospital_info,
        "news": news_items,
        "risks": risks,
        "opportunities": ops,
        "generated_at": datetime.utcnow().isoformat()
    }
    st.download_button(
        label="📥 Download JSON Dossier",
        data=json.dumps(dossier, indent=2),
        file_name=f"{org_name.replace(' ','_')}_profile.json",
        mime="application/json"
    )
