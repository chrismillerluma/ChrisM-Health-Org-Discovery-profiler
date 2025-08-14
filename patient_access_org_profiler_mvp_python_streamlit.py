import streamlit as st
import pandas as pd
import requests
import xml.etree.ElementTree as ET
import json
from datetime import datetime
from bs4 import BeautifulSoup

# ---- Load CMS Hospital Data ----
@st.cache_data
def load_cms_data():
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    try:
        df = pd.read_csv(url, dtype=str)
    except Exception as e:
        st.warning(f"Unable to load CMS data from web: {e}. Using local backup if available.")
        try:
            df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
        except Exception as e2:
            st.error(f"Local backup not found or empty: {e2}")
            return pd.DataFrame()
    return df

# ---- Get Google News ----
def get_news(org_name, max_items=5):
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ', '+')}"
    try:
        r = requests.get(rss_url)
        articles = []
        if r.status_code == 200:
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:max_items]:
                articles.append({
                    "title": item.find("title").text,
                    "link": item.find("link").text,
                    "date": item.find("pubDate").text
                })
        return articles
    except:
        return []

# ---- Get Google Reviews (Web Scraping) ----
def get_google_reviews(org_name, max_reviews=5):
    search_url = f"https://www.google.com/search?q={org_name.replace(' ', '+')}+reviews"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(search_url, headers=headers, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        reviews = []
        review_elements = soup.select("span span")[:max_reviews*2]  # rough approximation
        for el in review_elements:
            text = el.get_text()
            if text:
                reviews.append(text)
        # split positive/negative roughly by presence of words
        pos, neg = [], []
        for rev in reviews:
            rev_lower = rev.lower()
            if any(word in rev_lower for word in ["good","great","excellent","friendly","helpful"]):
                pos.append(rev)
            elif any(word in rev_lower for word in ["bad","poor","slow","rude","long wait"]):
                neg.append(rev)
        return {"positive": pos[:max_reviews], "negative": neg[:max_reviews]}
    except:
        return {"positive": [], "negative": []}

# ---- Assess Risks/Opportunities from CMS Data ----
def assess_risks_ops(row):
    risks, ops = [], []
    if row.get("Hospital overall rating") and row["Hospital overall rating"].isdigit():
        rating = int(row["Hospital overall rating"])
        if rating <= 2:
            risks.append("Low star rating — potential quality/perception issues.")
        elif rating >= 4:
            ops.append("High star rating — strong reputation advantage.")
    if row.get("Emergency Services") == "No":
        risks.append("No emergency services — may affect patient volume mix.")
    if "Government" in (row.get("Hospital ownership") or ""):
        ops.append("Government-owned — potential grant/public funding access.")
    return risks, ops

# ---- Streamlit App ----
st.title("🏥 Patient Access Org Profiler — Call Prep Highlights")
st.write("Enter any organization (hospital, health system, vendor) to get a public-data based pre-discovery profile.")

org_name = st.text_input("Organization Name")
df_cms = load_cms_data()

if org_name:
    # ---- CMS Match ----
    cms_matches = pd.DataFrame()
    if not df_cms.empty:
        cms_matches = df_cms[df_cms["Hospital Name"].str.contains(org_name, case=False, na=False)]
    
    facility_info = {}
    risks, ops = [], []
    if not cms_matches.empty:
        row = cms_matches.iloc[0].to_dict()
        facility_info = row
        risks, ops = assess_risks_ops(row)
    
    # ---- News ----
    news_items = get_news(org_name, max_items=5)
    
    # ---- Reviews ----
    reviews = get_google_reviews(org_name, max_reviews=5)
    
    # ---- Build Summary Highlights ----
    summary = {
        "strengths": [],
        "weaknesses": [],
        "challenges": [],
        "key_stats": {}
    }
    # From CMS
    if facility_info:
        summary["key_stats"] = {
            "Hospital Name": facility_info.get("Hospital Name"),
            "Overall Rating": facility_info.get("Hospital overall rating"),
            "Emergency Services": facility_info.get("Emergency Services"),
            "Ownership": facility_info.get("Hospital ownership")
        }
    summary["strengths"].extend(ops)
    summary["weaknesses"].extend(risks)
    summary["strengths"].extend(reviews["positive"])
    summary["weaknesses"].extend(reviews["negative"])
    
    # ---- Display Report ----
    st.subheader("📌 Summary Highlights")
    st.markdown("**Strengths / Positives:**")
    for s in summary["strengths"]: st.write(f"- {s}")
    st.markdown("**Weaknesses / Negatives:**")
    for w in summary["weaknesses"]: st.write(f"- {w}")
    st.markdown("**Key Stats:**")
    st.json(summary["key_stats"])
    
    st.subheader("🏥 Facility Information (CMS)")
    if facility_info:
        st.json(facility_info)
    else:
        st.write("No CMS data found.")
    
    st.subheader("📰 Recent News")
    if news_items:
        for article in news_items:
            st.markdown(f"- [{article['title']}]({article['link']}) ({article['date']})")
    else:
        st.write("No recent news found.")
    
    st.subheader("💬 Patient Reviews")
    st.markdown("**Positive Reviews:**")
    for r in reviews["positive"]: st.write(f"- {r}")
    st.markdown("**Negative Reviews:**")
    for r in reviews["negative"]: st.write(f"- {r}")
    
    # ---- Download JSON ----
    report = {
        "organization": org_name,
        "summary": summary,
        "facility_info": facility_info,
        "news": news_items,
        "reviews": reviews,
        "generated_at": datetime.utcnow().isoformat()
    }
    st.download_button(
        label="📥 Download Full JSON Report",
        data=json.dumps(report, indent=2),
        file_name=f"{org_name.replace(' ','_')}_report.json",
        mime="application/json"
    )
