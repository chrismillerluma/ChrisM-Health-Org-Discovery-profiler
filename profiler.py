import streamlit as st
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="Hospital Info Dashboard", layout="wide")
st.title("🏥 Hospital Info Dashboard")

# -------------------------------
# FUNCTIONS
# -------------------------------

# --- U.S. News Rankings ---
def fetch_usnews_rankings(hospital_name):
    url = f"https://health.usnews.com/best-hospitals/search?hospital_name={hospital_name.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        ranking = soup.find("div", class_="ranking")
        specialties = soup.find_all("div", class_="specialty")
        return {
            "ranking": ranking.text.strip() if ranking else "N/A",
            "specialties": [s.text.strip() for s in specialties] if specialties else []
        }
    except Exception as e:
        return {"error": f"Failed to fetch U.S. News data: {e}"}

# --- Yelp Reviews ---
def fetch_yelp_reviews(hospital_name, location="San Francisco, CA", limit=5):
    query = f"{hospital_name} {location} reviews"
    url = f"https://www.yelp.com/search?find_desc={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, "html.parser")
        reviews = []
        for review in soup.find_all("p", class_="comment__09f24__gu0rG"):
            reviews.append(review.text.strip())
            if len(reviews) >= limit:
                break
        return reviews
    except Exception as e:
        return [f"Failed to fetch Yelp reviews: {e}"]

# --- CMS HCAHPS Data ---
def fetch_hcahps_data(hospital_id):
    url = f"https://data.cms.gov/provider-data/api/1/datastore/query/hospitals/{hospital_id}/hcahps"
    try:
        response = requests.get(url)
        data = response.json()
        hcahps_scores = {
            "overall_rating": data.get("overall_rating", "N/A"),
            "recommendation": data.get("recommendation", "N/A")
        }
        return hcahps_scores
    except Exception as e:
        return {"error": f"Failed to fetch HCAHPS data: {e}"}

# -------------------------------
# USER INPUT
# -------------------------------
hospital_name = st.text_input("Enter Hospital Name", "UCSF Medical Center")
hospital_id = st.text_input("Enter CMS Hospital ID", "050454")  # Replace with actual hospital CMS ID

if hospital_name and hospital_id:
    # -------------------------------
    # U.S. News Rankings
    # -------------------------------
    with st.spinner("Fetching U.S. News Rankings..."):
        usnews_data = fetch_usnews_rankings(hospital_name)
        st.subheader("📰 U.S. News & World Report Rankings")
        if "error" not in usnews_data:
            st.write(f"**Ranking:** {usnews_data['ranking']}")
            st.write("**Top Specialties:**")
            for specialty in usnews_data["specialties"]:
                st.write(f"- {specialty}")
        else:
            st.error(usnews_data["error"])

    # -------------------------------
    # Yelp Reviews
    # -------------------------------
    with st.spinner("Fetching Yelp Reviews..."):
        yelp_reviews = fetch_yelp_reviews(hospital_name)
        st.subheader("⭐ Yelp Reviews")
        for review in yelp_reviews:
            st.write(f"- {review}")

    # -------------------------------
    # CMS HCAHPS Data
    # -------------------------------
    with st.spinner("Fetching CMS HCAHPS Patient Survey Data..."):
        hcahps_data = fetch_hcahps_data(hospital_id)
        st.subheader("📊 CMS Patient Survey (HCAHPS) Scores")
        if "error" not in hcahps_data:
            st.write(f"**Overall Rating:** {hcahps_data['overall_rating']}")
            st.write(f"**Would Recommend Hospital:** {hcahps_data['recommendation']}")
        else:
            st.error(hcahps_data["error"])
