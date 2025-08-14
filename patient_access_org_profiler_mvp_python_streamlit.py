import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
from rapidfuzz import process, fuzz
import time

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

def log(msg, log_list):
    """Append log message"""
    log_list.append(msg)
    st.session_state['log_area'] = "\n".join(log_list)

def fetch_source(url, log_list, desc, parse_fn=None):
    """Generic fetch function with logging"""
    log(f"Fetching {desc}...", log_list)
    headers = {"User-Agent":"Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and parse_fn:
            return parse_fn(r)
        return r.text
    except Exception as e:
        log(f"{desc} fetch error: {e}", log_list)
        return []

def parse_news(r):
    """Parse news from RSS feed"""
    soup = BeautifulSoup(r, features="xml")
    articles = []
    for item in soup.find_all("item")[:5]:
        articles.append({
            "title": item.title.text,
            "link": item.link.text,
            "pubDate": item.pubDate.text
        })
    return articles

def parse_reviews_generic(r):
    """Extract meaningful text snippets for generic sources"""
    soup = BeautifulSoup(r, "html.parser")
    snippets = []
    for p in soup.find_all("p"):
        text = p.get_text().strip()
        if len(text) > 20:
            snippets.append(text)
    return snippets[:5]

def parse_yelp_reviews(r):
    """Yelp scraping - get snippet + rating if possible"""
    soup = BeautifulSoup(r, "html.parser")
    reviews = []
    for div in soup.find_all("div", {"class":"review__373c0__13kpL"}):
        rating_div = div.find("div", {"role":"img"})
        rating = rating_div["aria-label"] if rating_div else None
        text = div.find("span")
        text = text.get_text().strip() if text else ""
        if text:
            reviews.append({"rating": rating, "snippet": text})
    return reviews[:5]

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

if 'log_area' not in st.session_state:
    st.session_state['log_area'] = ""

log_window = st.text_area("Progress Log", value=st.session_state['log_area'], height=200)

progress = st.progress(0)

df_cms = load_cms_data()
log_list = []

if org_name_input:
    st.info("Searching CMS database for best matches...")
    matches = fuzzy_search(org_name_input, df_cms["Hospital Name"].tolist())
    st.write("Top matches from CMS data (fuzzy):")
    st.write(matches)
    progress.progress(10)

    if matches:
        best_match_name = matches[0][0]
        row = df_cms[df_cms["Hospital Name"]==best_match_name].iloc[0].to_dict()
        st.subheader("🏥 Facility Information")
        st.json(row)
        progress.progress(20)

        # Fetching multiple sources with progress updates
        news = fetch_source(f"https://news.google.com/rss/search?q={org_name_input.replace(' ','+')}", log_list, "News", parse_news)
        progress.progress(35)
        google_reviews = fetch_source(f"https://www.google.com/search?q={org_name_input.replace(' ','+') + '+reviews'}", log_list, "Google Reviews", parse_reviews_generic)
        progress.progress(50)
        yelp_reviews = fetch_source(f"https://www.yelp.com/search?find_desc={org_name_input.replace(' ','+')}", log_list, "Yelp Reviews", parse_yelp_reviews)
        progress.progress(65)
        ratemds_reviews = fetch_source(f"https://www.ratemds.com/search/?q={org_name_input.replace(' ','+')}", log_list, "RateMDs Reviews", parse_reviews_generic)
        progress.progress(80)
        healthgrades_reviews = fetch_source(f"https://www.healthgrades.com/usearch?what={org_name_input.replace(' ','+')}", log_list, "Healthgrades Reviews", parse_reviews_generic)
        progress.progress(95)

        progress.progress(100)

        # Display News
        st.subheader("📰 Recent News")
        if news:
            for article in news:
                st.markdown(f"- [{article['title']}]({article['link']}) ({article['pubDate']})")
        else:
            st.write("No news found.")

        # Display Reviews
        st.subheader("⭐ Reviews Highlights")
        st.markdown("**Google:**"); st.write(google_reviews)
        st.markdown("**Yelp:**"); st.write(yelp_reviews)
        st.markdown("**RateMDs:**"); st.write(ratemds_reviews)
        st.markdown("**Healthgrades:**"); st.write(healthgrades_reviews)

        # Risks & Opportunities
        st.subheader("⚠️ Risks & 💡 Opportunities")
        risks, ops = assess_facility(row)
        st.markdown("**Risks:**")
        for r in risks: st.write(f"- {r}")
        st.markdown("**Opportunities:**")
        for o in ops: st.write(f"- {o}")

        # JSON download
        dossier = {
            "facility_info": row,
            "news": news,
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
