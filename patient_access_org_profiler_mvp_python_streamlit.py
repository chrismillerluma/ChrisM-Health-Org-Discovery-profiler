import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
import json
from datetime import datetime

# ---- Load CMS Hospital Data ----
@st.cache_data
def load_cms_data():
    url = "https://data.medicare.gov/api/views/xubh-q36u/rows.csv?accessType=DOWNLOAD"
    try:
        df = pd.read_csv(url, dtype=str)
        st.success("CMS data loaded from web.")
    except Exception:
        try:
            df = pd.read_csv("cms_hospitals_backup.csv", dtype=str)
            st.warning("Unable to load CMS data from web. Using local backup if available.")
        except Exception:
            st.error("CMS data not available.")
            df = pd.DataFrame()
    return df

# ---- Fuzzy name matching ----
def match_org_name(name, choices, limit=5):
    matches = process.extract(name, choices, scorer=fuzz.WRatio, limit=limit)
    return matches

# ---- Scrape Google News ----
def get_news(org_name):
    rss_url = f"https://news.google.com/rss/search?q={org_name.replace(' ','+')}"
    try:
        r = requests.get(rss_url, timeout=10)
        root = BeautifulSoup(r.content, features="xml")
        items = root.findAll("item")[:5]
        articles = []
        for item in items:
            articles.append({
                "title": item.title.text,
                "link": item.link.text,
                "date": item.pubDate.text
            })
        return articles
    except:
        return []

# ---- Scrape Google Reviews (basic) ----
def get_google_reviews(org_name):
    search_url = f"https://www.google.com/search?q={org_name.replace(' ','+')+ '+reviews'}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(search_url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        reviews = []
        for div in soup.find_all("div"):
            text = div.get_text().strip()
            if len(text) > 50:
                reviews.append(text)
        return reviews[:5]
    except:
        return []

# ---- Assess Risks & Opportunities ----
def assess_risks_ops(row):
    risks, ops = [], []
    rating = row.get("Hospital overall rating")
    if rating and rating.isdigit():
        rating = int(rating)
        if rating <= 2: risks.append("Low star rating — potential quality/perception issues.")
        elif rating >= 4: ops.append("High star rating — leverage strong reputation.")
    if row.get("Emergency Services") == "No":
        risks.append("No emergency services — may affect patient volume mix.")
    if "Government" in (row.get("Hospital ownership") or ""):
        ops.append("Government-owned — may have grant or public funding access.")
    return risks, ops

# ---- Streamlit UI ----
st.title("🏥 Patient Access Org Profiler — Full Report")

org_input = st.text_input("Organization / Vendor Name")

df_cms = load_cms_data()

if org_input and not df_cms.empty:
    matches = match_org_name(org_input, df_cms["Hospital Name"].tolist(), limit=5)
    st.subheader("Matching Organizations (Fuzzy)")
    for m in matches:
        st.write(f"{m[0]} — Score: {m[1]}")

    best_match = matches[0][0]
    st.info(f"Using best match: {best_match}")

    row = df_cms[df_cms["Hospital Name"]==best_match].iloc[0].to_dict()

    st.subheader("🏥 Facility Info")
    st.json(row)

    st.subheader("📰 Recent News")
    news_items = get_news(best_match)
    if news_items:
        for n in news_items:
            st.markdown(f"- [{n['title']}]({n['link']}) ({n['date']})")
    else:
        st.write("No recent news found.")

    st.subheader("🌟 Patient Reviews / Feedback")
    reviews = get_google_reviews(best_match)
    if reviews:
        for r in reviews:
            st.write(f"- {r}")
    else:
        st.write("No reviews found.")

    st.subheader("⚠️ Risks & 💡 Opportunities")
    risks, ops = assess_risks_ops(row)
    st.markdown("**Risks:**")
    for r in risks: st.write(f"- {r}")
    st.markdown("**Opportunities:**")
    for o in ops: st.write(f"- {o}")

    # ---- JSON download ----
    dossier = {
        "organization": best_match,
        "facility_info": row,
        "news": news_items,
        "reviews": reviews,
        "risks": risks,
        "opportunities": ops,
        "generated_at": datetime.now().isoformat()
    }
    st.download_button(
        "📥 Download JSON Dossier",
        data=json.dumps(dossier, indent=2),
        file_name=f"{best_match.replace(' ','_')}_profile.json",
        mime="application/json"
    )
