import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time
from rapidfuzz import process, fuzz

# --------------------------
# Helper functions
# --------------------------

@st.cache_data
def load_cms_data():
    """Load CMS Hospital General Information"""
    try:
        url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
        df = pd.read_csv(url, dtype=str)
        return df
    except:
        st.warning("Unable to load CMS data from web. Using local backup if available.")
        try:
            df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
            return df
        except:
            st.error("No CMS data available.")
            return pd.DataFrame()

def fuzzy_search(name, choices, limit=5):
    """Return top fuzzy matches"""
    results = process.extract(name, choices, scorer=fuzz.WRatio, limit=limit)
    return results

def fetch_news(org_name, log_func):
    """Fetch recent news from Google News RSS"""
    log_func("Fetching news...")
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ','+')}"
    articles = []
    try:
        r = requests.get(rss_url, timeout=10)
        if r.status_code == 200:
            root = BeautifulSoup(r.content, features="xml")
            for item in root.find_all("item")[:5]:
                articles.append({
                    "title": item.title.text,
                    "link": item.link.text,
                    "pubDate": item.pubDate.text
                })
        return articles
    except Exception as e:
        log_func(f"Error fetching news: {e}")
        return []

def fetch_reviews_google(org_name, log_func):
    """Scrape basic Google search results for reviews summary"""
    log_func("Fetching Google reviews summary...")
    search_url = f"https://www.google.com/search?q={org_name.replace(' ','+') + '+reviews'}"
    headers = {"User-Agent":"Mozilla/5.0"}
    reviews = []
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        snippets = soup.find_all("span")
        for s in snippets[:5]:
            reviews.append(s.get_text())
        return reviews
    except Exception as e:
        log_func(f"Google reviews fetch error: {e}")
        return []

def fetch_reviews_yelp(org_name, log_func):
    """Scrape Yelp search page for review snippets"""
    log_func("Fetching Yelp reviews summary...")
    search_url = f"https://www.yelp.com/search?find_desc={org_name.replace(' ','+')}"
    headers = {"User-Agent":"Mozilla/5.0"}
    reviews = []
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for snippet in soup.find_all("p")[:5]:
            reviews.append(snippet.get_text())
        return reviews
    except Exception as e:
        log_func(f"Yelp reviews fetch error: {e}")
        return []

def fetch_reviews_ratemds(org_name, log_func):
    """Scrape RateMDs reviews"""
    log_func("Fetching RateMDs reviews...")
    search_url = f"https://www.ratemds.com/search/?q={org_name.replace(' ','+')}"
    headers = {"User-Agent":"Mozilla/5.0"}
    reviews = []
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for snippet in soup.find_all("p")[:5]:
            reviews.append(snippet.get_text())
        return reviews
    except Exception as e:
        log_func(f"RateMDs fetch error: {e}")
        return []

def fetch_reviews_healthgrades(org_name, log_func):
    """Scrape Healthgrades reviews"""
    log_func("Fetching Healthgrades reviews...")
    search_url = f"https://www.healthgrades.com/usearch?what={org_name.replace(' ','+')}"
    headers = {"User-Agent":"Mozilla/5.0"}
    reviews = []
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for snippet in soup.find_all("p")[:5]:
            reviews.append(snippet.get_text())
        return reviews
    except Exception as e:
        log_func(f"Healthgrades fetch error: {e}")
        return []

def assess_facility(row):
    """Summarize key CMS info"""
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

# --------------------------
# Streamlit UI
# --------------------------

st.title("🏥 Patient Access Org Profiler — Sales Call Prep")

org_name_input = st.text_input("Organization or Vendor Name")

log_window = st.empty()  # placeholder for log/progress

def log(msg):
    log_window.text_area("Progress", value=msg, height=200)

df_cms = load_cms_data()

if org_name_input:
    st.info("Searching CMS database for best matches...")
    matches = fuzzy_search(org_name_input, df_cms["Hospital Name"].tolist())
    st.write("Top matches from CMS data (fuzzy):")
    st.write(matches)

    if matches:
        best_match_name = matches[0][0]
        row = df_cms[df_cms["Hospital Name"]==best_match_name].iloc[0].to_dict()

        st.subheader("🏥 Facility Information")
        st.json(row)

        # Fetch data from multiple sources
        all_news = fetch_news(org_name_input, log)
        google_reviews = fetch_reviews_google(org_name_input, log)
        yelp_reviews = fetch_reviews_yelp(org_name_input, log)
        ratemds_reviews = fetch_reviews_ratemds(org_name_input, log)
        healthgrades_reviews = fetch_reviews_healthgrades(org_name_input, log)

        st.subheader("📰 Recent News")
        if all_news:
            for article in all_news:
                st.markdown(f"- [{article['title']}]({article['link']}) ({article['pubDate']})")
        else:
            st.write("No news found.")

        st.subheader("⭐ Reviews Highlights")
        st.markdown("**Google:**"); st.write(google_reviews)
        st.markdown("**Yelp:**"); st.write(yelp_reviews)
        st.markdown("**RateMDs:**"); st.write(ratemds_reviews)
        st.markdown("**Healthgrades:**"); st.write(healthgrades_reviews)

        st.subheader("⚠️ Risks & 💡 Opportunities")
        risks, ops = assess_facility(row)
        st.markdown("**Risks:**")
        for r in risks: st.write(f"- {r}")
        st.markdown("**Opportunities:**")
        for o in ops: st.write(f"- {o}")

        # Download JSON report
        dossier = {
            "facility_info": row,
            "news": all_news,
            "reviews": {
                "google": google_reviews,
                "yelp": yelp_reviews,
                "ratemds": ratemds_reviews,
                "healthgrades": healthgrades_reviews
            },
            "risks": risks,
            "opportunities": ops,
            "generated_at": datetime.utcnow().isoformat()
        }
        st.download_button(
            label="📥 Download Full Report JSON",
            data=json.dumps(dossier, indent=2),
            file_name=f"{org_name_input.replace(' ','_')}_profile.json",
            mime="application/json"
        )
