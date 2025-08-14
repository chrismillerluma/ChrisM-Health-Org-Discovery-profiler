import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime

# ---- Load CMS Hospital General Information ----
@st.cache_data
def load_cms_data():
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    try:
        df = pd.read_csv(url, dtype=str)
    except Exception as e:
        st.warning(f"⚠️ Could not fetch live CMS data ({e}). Using local backup instead.")
        df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
    return df

# ---- Get News from Google News RSS ----
def get_news(org_name):
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ', '+')}"
    articles = []
    try:
        r = requests.get(rss_url, timeout=5)
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:5]:
                title = item.find("title").text
                link = item.find("link").text
                pub_date = item.find("pubDate").text
                articles.append({
                    "title": title,
                    "link": link,
                    "date": pub_date
                })
    except Exception as e:
        st.warning(f"⚠️ Could not fetch news: {e}")
    return articles

# ---- Simple Risk/Opportunity Generator ----
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

# ---- Streamlit UI ----
st.title("🏥 Patient Access Org Profiler — No Secrets Version")
st.write("Enter a hospital or health system name to get a quick pre-discovery profile using only public data.")

org_name = st.text_input("Organization Name")
df_cms = load_cms_data()

if org_name:
    matches = df_cms[df_cms["Hospital Name"].str.contains(org_name, case=False, na=False)]
    if matches.empty:
        st.warning("No matches found in CMS Hospital General Information data.")
    else:
        st.success(f"Found {len(matches)} matches — showing first result.")
        row = matches.iloc[0].to_dict()

        st.subheader("🏥 Facility Information")
        st.json(row)

        st.subheader("📰 Recent News")
        news_items = get_news(org_name)
        if news_items:
            for article in news_items:
                st.markdown(f"- [{article['title']}]({article['link']}) ({article['date']})")
        else:
            st.write("No recent news found.")

        st.subheader("⚠️ Risks & 💡 Opportunities")
        risks, ops = assess_risks_ops(row)
        st.markdown("**Risks:**")
        for r in risks: st.write(f"- {r}")
        st.markdown("**Opportunities:**")
        for o in ops: st.write(f"- {o}")

        # Download JSON
        dossier = {
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
