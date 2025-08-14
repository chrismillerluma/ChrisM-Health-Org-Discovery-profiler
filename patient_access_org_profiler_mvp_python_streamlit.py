import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from difflib import get_close_matches

# ---- Load CMS Hospital General Information ----
@st.cache_data
def load_cms_data():
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    try:
        df = pd.read_csv(url, dtype=str)
        st.info("✅ Loaded CMS hospital data from web.")
        return df
    except Exception:
        st.warning("⚠️ Unable to load CMS data from web. Trying local backup.")
        try:
            df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
            st.info("✅ Loaded CMS hospital data from local backup.")
            return df
        except Exception:
            st.error("❌ No CMS data available.")
            return pd.DataFrame()

# ---- Google News RSS ----
def get_news(org_name, max_articles=5):
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ', '+')}"
    articles = []
    try:
        r = requests.get(rss_url, timeout=5)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:max_articles]:
                articles.append({
                    "title": item.find("title").text,
                    "link": item.find("link").text,
                    "date": item.find("pubDate").text
                })
    except Exception:
        st.warning(f"Could not fetch news for {org_name}.")
    return articles

# ---- Risk & Opportunity Assessment ----
def assess_risks_ops(row):
    risks, ops = [], []
    rating = row.get("Hospital overall rating")
    if rating and rating.isdigit():
        rating = int(rating)
        if rating <= 2:
            risks.append("Low star rating — potential quality/perception issues.")
        elif rating >= 4:
            ops.append("High star rating — leverage strong reputation.")
    if row.get("Emergency Services") == "No":
        risks.append("No emergency services — may affect patient volume mix.")
    ownership = row.get("Hospital ownership", "")
    if "Government" in ownership:
        ops.append("Government-owned — may have grant or public funding access.")
    return risks, ops

# ---- Fuzzy search helper ----
def fuzzy_search(df, search_col, query, cutoff=0.6):
    if df.empty:
        return []
    names = df[search_col].dropna().tolist()
    matches = get_close_matches(query, names, n=10, cutoff=cutoff)
    return matches

# ---- Streamlit UI ----
st.set_page_config(page_title="Patient / Vendor Org Profiler", layout="wide")
st.title("🏥 Patient / Vendor Organization Profiler (Enhanced)")

st.write("""
Enter a hospital, health system, or vendor name to generate a quick profile using public data.
The profile includes facility information, recent news, risks & opportunities, and a JSON dossier for download.
""")

org_name = st.text_input("Organization / Vendor Name")
df_cms = load_cms_data()

selected_org = None

if org_name:
    # Fuzzy match CMS hospitals
    matches = fuzzy_search(df_cms, "Hospital Name", org_name)
    
    if matches:
        st.subheader("⚡ Possible matches found in CMS data:")
        selected_org = st.selectbox("Select an organization", matches)
        row = df_cms[df_cms["Hospital Name"] == selected_org].iloc[0].to_dict()
        st.subheader("🏥 Facility Information")
        st.json(row)
    else:
        st.warning("No CMS matches found. Showing general profile only.")
        row = {}

    # News
    st.subheader("📰 Recent News")
    news_items = get_news(org_name)
    if news_items:
        for article in news_items:
            st.markdown(f"- [{article['title']}]({article['link']}) ({article['date']})")
    else:
        st.write("No recent news found.")

    # Risks & Opportunities
    st.subheader("⚠️ Risks & 💡 Opportunities")
    risks, ops = assess_risks_ops(row)
    st.markdown("**Risks:**")
    if risks:
        for r in risks: st.write(f"- {r}")
    else:
        st.write("- None detected")
    st.markdown("**Opportunities:**")
    if ops:
        for o in ops: st.write(f"- {o}")
    else:
        st.write("- None detected")

    # JSON Dossier
    dossier = {
        "organization": selected_org if selected_org else org_name,
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
