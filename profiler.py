import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from rapidfuzz import process, fuzz
from datetime import datetime
import io
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="Healthcare Profiler", layout="wide")
st.title("Healthcare Organization Discovery Profiler")

CMS_URL = "https://data.cms.gov/provider-data/sites/default/files/resources/893c372430d9d71a1c52737d01239d47_1753409109/Hospital_General_Information.csv"

# -------------------------
# Helper Functions
# -------------------------

# Validate org name against CMS list
@st.cache_data
def load_cms_names():
    r = requests.get(CMS_URL, timeout=15)
    df = pd.read_csv(io.BytesIO(r.content))
    return df['hospital_name'].tolist(), df

def fuzzy_match_name(name, name_list, threshold=80):
    match, score = process.extractOne(name, name_list, scorer=fuzz.WRatio)
    return match if score >= threshold else None

# Fetch website data
def scrape_website(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        return soup.title.string if soup.title else "No title found"
    except:
        return "Website not reachable"

# Placeholder for reviews/news scraping
def get_reviews(org_name):
    return f"Fetched reviews for {org_name} (dummy data)"

def get_news(org_name):
    return f"Fetched news for {org_name} (dummy data)"

# -------------------------
# UI: Input and Validation
# -------------------------

org_input = st.text_input("Enter healthcare organization name:")

if org_input:
    st.info("Validating organization name...")
    cms_names, cms_df = load_cms_names()
    valid_name = fuzzy_match_name(org_input, cms_names)
    if valid_name:
        st.success(f"Organization validated: {valid_name}")
        
        # Wait for user click
        if st.button("Search Organization"):
            
            # Fetch CMS info for this hospital
            org_data = cms_df[cms_df['hospital_name'] == valid_name].to_dict(orient="records")[0]

            st.subheader("CMS Data")
            st.json(org_data)

            # Parallel fetch: website, news, reviews
            def fetch_all():
                website_result = scrape_website(org_data.get("website", ""))
                news_result = get_news(valid_name)
                reviews_result = get_reviews(valid_name)
                return website_result, news_result, reviews_result

            with ThreadPoolExecutor() as executor:
                website_result, news_result, reviews_result = executor.submit(fetch_all).result()

            st.subheader("Website Info")
            st.write(website_result)

            st.subheader("News")
            st.write(news_result)

            st.subheader("Reviews")
            st.write(reviews_result)
    else:
        st.error("Organization not found in CMS database. Check spelling or try another name.")
