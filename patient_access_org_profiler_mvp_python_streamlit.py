# patient_access_org_profiler_final.py

import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime, timezone
import json
import re

st.set_page_config(page_title="Patient Access Org Profiler", layout="wide")

# ---------------------
# Helper Functions
# ---------------------

@st.cache_data
def load_cms_data():
    """
    Load CMS Hospital General Information data from web with local backup fallback.
    """
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    backup_file = "cms_hospitals_backup.csv"
    try:
        df = pd.read_csv(url, dtype=str)
        st.success("Loaded CMS hospital data from web.")
    except Exception as e:
        st.warning("Unable to load CMS data from web. Attempting local backup...")
        try:
            df = pd.read_csv(backup_file, dtype=str)
            st.success("Loaded CMS hospital data from local backup.")
        except Exception as e2:
            st.error("Failed to load CMS hospital data.")
            df = pd.DataFrame()
    return df

def fuzzy_match_name(name, choices, limit=5):
    """
    Use fuzzy matching to find closest hospital names from CMS.
    """
    results = process.extract(name, choices, scorer=fuzz.WRatio, limit=limit)
    return results

def get_google_news(org_name, max_items=5):
    """
    Scrape Google News RSS feed for recent news articles about the organization.
    """
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ', '+')}"
    articles = []
    try:
        r = requests.get(rss_url, timeout=10)
        if r.status_code == 200:
            root = BeautifulSoup(r.content, "xml")
            items = root.find_all("item")[:max_items]
            for item in items:
                articles.append({
                    "title": item.title.text,
                    "link": item.link.text,
                    "pubDate": item.pubDate.text
                })
    except Exception as e:
        st.warning("Unable to fetch news.")
    return articles

def get_patient_reviews(org_name, max_items=5):
    """
    Scrape patient reviews from Google search results.
    Note: Limited and basic due to no API.
    """
    query = f"{org_name} hospital reviews site:healthgrades.com OR site:yelp.com"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    reviews = []
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "html.parser")
            snippets = soup.find_all("span")
            for s in snippets:
                text = s.get_text()
                if len(text) > 50 and len(reviews) < max_items:
                    reviews.append(text)
    except Exception as e:
        st.warning("Unable to fetch reviews from Google.")
    return reviews

def assess_risks_ops(row):
    """
    Highlight potential risks and opportunities based on CMS data.
    """
    risks, ops = [], []
    try:
        if row.get("Hospital overall rating") and row["Hospital overall rating"].isdigit():
            rating = int(row["Hospital overall rating"])
            if rating <= 2:
                risks.append("Low star rating — potential quality/perception issues.")
            elif rating >= 4:
                ops.append("High star rating — strong reputation to leverage.")
        if row.get("Emergency Services") == "No":
            risks.append("No emergency services — may affect patient volume mix.")
        if "Government" in (row.get("Hospital ownership") or ""):
            ops.append("Government-owned — may have grant or public funding access.")
    except Exception as e:
        st.warning("Error evaluating risks/opportunities.")
    return risks, ops

# ---------------------
# Main Streamlit UI
# ---------------------

st.title("🏥 Patient Access Org Profiler — Comprehensive Public Data Report")
st.write("Enter a hospital, health system, or vendor name to generate a pre-discovery profile.")

org_input = st.text_input("Organization Name", value="UCSF Medical Center")

df_cms = load_cms_data()

if not df_cms.empty and org_input:
    # Fuzzy match to CMS hospital names
    cms_names = df_cms["Hospital Name"].dropna().tolist()
    matches = fuzzy_match_name(org_input, cms_names, limit=5)

    if matches:
        best_match_name = matches[0][0]
        st.subheader(f"Best Match: {best_match_name}")
        row = df_cms[df_cms["Hospital Name"] == best_match_name].iloc[0].to_dict()

        # Facility Info
        st.subheader("🏥 Facility Information (CMS Data)")
        st.json(row)

        # News
        st.subheader("📰 Recent News")
        news_items = get_google_news(best_match_name, max_items=5)
        if news_items:
            for article in news_items:
                st.markdown(f"- [{article['title']}]({article['link']}) ({article['pubDate']})")
        else:
            st.write("No recent news found.")

        # Patient Reviews
        st.subheader("💬 Patient Reviews Highlights")
        reviews = get_patient_reviews(best_match_name, max_items=5)
        if reviews:
            for r in reviews:
                st.write(f"- {r}")
        else:
            st.write("No reviews found.")

        # Risks & Opportunities
        st.subheader("⚠️ Risks & 💡 Opportunities")
        risks, ops = assess_risks_ops(row)
        st.markdown("**Risks:**")
        for r in risks: st.write(f"- {r}")
        st.markdown("**Opportunities:**")
        for o in ops: st.write(f"- {o}")

        # Summary
        st.subheader("📋 Summary")
        st.markdown(f"""
        **Organization:** {best_match_name}  
        **CMS Rating:** {row.get('Hospital overall rating', 'N/A')}  
        **Number of News Articles:** {len(news_items)}  
        **Number of Reviews:** {len(reviews)}  
        **Generated At:** {datetime.now(timezone.utc).isoformat()}
        """)

        # Download JSON Dossier
        dossier = {
            "facility_info": row,
            "news": news_items,
            "patient_reviews": reviews,
            "risks": risks,
            "opportunities": ops,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        st.download_button(
            label="📥 Download JSON Dossier",
            data=json.dumps(dossier, indent=2),
            file_name=f"{best_match_name.replace(' ','_')}_profile.json",
            mime="application/json"
        )
    else:
        st.warning("No matching CMS hospital found.")
else:
    st.error("CMS data unavailable or organization name not entered.")
