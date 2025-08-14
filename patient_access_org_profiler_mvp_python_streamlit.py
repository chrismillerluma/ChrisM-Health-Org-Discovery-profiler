import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

# ---- Load CMS Hospital Data ----
@st.cache_data(show_spinner=True)
def load_cms_data():
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    try:
        df = pd.read_csv(url, dtype=str)
        if df.empty:
            raise ValueError("Live CMS data is empty")
        return df
    except Exception as e:
        st.warning(f"⚠️ Could not fetch live CMS data ({e}). Using backup CSV instead.")
        try:
            df_backup = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
            if df_backup.empty:
                raise ValueError("Backup CSV is empty")
            return df_backup
        except Exception as e2:
            st.error(f"Critical error: unable to load any CMS data ({e2})")
            return pd.DataFrame()  # empty fallback

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
    if "Hospital Name" in row:
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
st.title("🏥 Patient Access / Vendor Org Profiler")
st.write("Enter any organization or vendor name to generate a pre-discovery profile using only public data.")

org_name = st.text_input("Organization or Vendor Name")
df_cms = load_cms_data()

if org_name:
    if not df_cms.empty:
        matches = df_cms[df_cms["Hospital Name"].str.contains(org_name, case=False, na=False)]
    else:
        matches = pd.DataFrame()

    if matches.empty:
        st.info("No hospital matches found. Treating as vendor or non-hospital organization.")
        row = {"Name": org_name}
        risks, ops = [], []
    else:
        st.success(f"Found {len(matches)} hospital match(es). Showing first result.")
        row = matches.iloc[0].to_dict()
        risks, ops = assess_risks_ops(row)

    # ---- Facility / Vendor Info ----
    st.subheader("🏢 Organization Information")
    st.json(row)

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
        "facility_info": row,
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
