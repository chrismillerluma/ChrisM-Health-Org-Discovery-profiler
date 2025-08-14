import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

# ---- Load CMS Hospital Data (Backup CSV) ----
@st.cache_data
def load_cms_data():
    try:
        url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
        df = pd.read_csv(url, dtype=str)
        return df
    except Exception:
        st.warning("Unable to load CMS data from web. Using local backup if available.")
        try:
            df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
            return df
        except FileNotFoundError:
            st.error("No CMS data available. Some features will be limited.")
            return pd.DataFrame()

# ---- Fetch Google News ----
def get_news(org_name):
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ','+')}"
    articles = []
    try:
        r = requests.get(rss_url, timeout=5)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:5]:
                title = item.find("title").text
                link = item.find("link").text
                pub_date = item.find("pubDate").text
                articles.append({"title": title, "link": link, "date": pub_date})
    except Exception:
        pass
    return articles

# ---- Basic Risk/Opportunity Assessment ----
def assess_risks_ops(row):
    risks, ops = [], []
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

# ---- Match org/vendor in CMS data (simple substring search) ----
def match_organization(name, df):
    if df.empty:
        return None
    matches = df[df["Hospital Name"].str.contains(name, case=False, na=False)]
    if not matches.empty:
        return matches.iloc[0].to_dict()
    return None

# ---- Streamlit UI ----
st.title("🏥 Patient Access Org & Vendor Profiler")
st.write("Enter an organization or vendor name to get a quick pre-discovery profile using public data.")

org_name = st.text_input("Organization / Vendor Name")
df_cms = load_cms_data()

if org_name:
    st.subheader("🏥 CMS Facility Info (if applicable)")
    facility_info = match_organization(org_name, df_cms)
    if facility_info:
        st.json(facility_info)
        risks, ops = assess_risks_ops(facility_info)
    else:
        st.info("No CMS hospital match found — showing news and generic assessment.")
        facility_info = {}
        risks, ops = [], []

    st.subheader("📰 Recent News")
    news_items = get_news(org_name)
    if news_items:
        for article in news_items:
            st.markdown(f"- [{article['title']}]({article['link']}) ({article['date']})")
    else:
        st.write("No recent news found.")

    st.subheader("⚠️ Risks & 💡 Opportunities")
    if risks:
        st.markdown("**Risks:**")
        for r in risks: st.write(f"- {r}")
    if ops:
        st.markdown("**Opportunities:**")
        for o in ops: st.write(f"- {o}")
    if not risks and not ops:
        st.write("No specific risks or opportunities identified from available data.")

    # ---- Download JSON ----
    dossier = {
        "organization_name": org_name,
        "facility_info": facility_info,
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
