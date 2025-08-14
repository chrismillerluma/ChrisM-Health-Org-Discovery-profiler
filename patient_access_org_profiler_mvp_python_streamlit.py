import streamlit as st
import pandas as pd
import json
from datetime import datetime
from rapidfuzz import process, fuzz

# -----------------------
# Simulated CMS / Org Data
# -----------------------
def load_cms_data_sim():
    data = [
        {
            "Hospital Name": "Saint Mary Medical Center",
            "Hospital Type": "Acute Care",
            "Hospital Ownership": "Government - Local",
            "Emergency Services": "Yes",
            "Hospital Overall Rating": "4",
            "Total Licensed Beds": "250",
            "City": "Springfield",
            "State": "IL",
            "ER Wait Time": "25 min",
            "Specialties": "Cardiology, Orthopedics, Neurology",
            "Annual Patient Volume": "12,000"
        },
        {
            "Hospital Name": "Green Valley Clinic",
            "Hospital Type": "Specialty",
            "Hospital Ownership": "Private",
            "Emergency Services": "No",
            "Hospital Overall Rating": "2",
            "Total Licensed Beds": "50",
            "City": "Greenville",
            "State": "CA",
            "ER Wait Time": "N/A",
            "Specialties": "Dermatology, Endocrinology",
            "Annual Patient Volume": "2,500"
        },
        {
            "Hospital Name": "Lakeside Health",
            "Hospital Type": "Acute Care",
            "Hospital Ownership": "Private",
            "Emergency Services": "Yes",
            "Hospital Overall Rating": "3",
            "Total Licensed Beds": "180",
            "City": "Lakeside",
            "State": "NY",
            "ER Wait Time": "40 min",
            "Specialties": "Pediatrics, Oncology, Surgery",
            "Annual Patient Volume": "8,000"
        },
    ]
    return pd.DataFrame(data)

# -----------------------
# Simulated News / Reviews
# -----------------------
def get_news_sim(org_name):
    return [
        {"title": f"{org_name} launches new patient portal", "link": "#", "date": "2025-08-01"},
        {"title": f"Patient satisfaction rises at {org_name}", "link": "#", "date": "2025-07-15"},
        {"title": f"{org_name} faces staffing shortage", "link": "#", "date": "2025-06-30"},
    ]

def get_reviews_sim(org_name):
    return [
        {"source": "Google Reviews", "text": "Excellent care and friendly staff."},
        {"source": "Healthgrades", "text": "Long wait times in the ER."},
        {"source": "Yelp", "text": "Clean facilities but difficult parking."},
        {"source": "Reddit", "text": "Highly recommend for cardiology treatments."},
        {"source": "Twitter", "text": "Staff was rude, but treatment was effective."}
    ]

# -----------------------
# Highlights / Stats
# -----------------------
def assess_highlights(row):
    highlights = {"positives": [], "negatives": [], "stats": []}
    rating = int(row.get("Hospital Overall Rating", "0"))
    if rating >= 4:
        highlights["positives"].append("High patient rating — strong reputation.")
    elif rating <= 2:
        highlights["negatives"].append("Low patient rating — potential quality concerns.")

    if row.get("Emergency Services") == "Yes":
        highlights["positives"].append("Offers emergency services.")
    else:
        highlights["negatives"].append("No emergency services — may limit patient volume.")

    beds = row.get("Total Licensed Beds")
    if beds:
        highlights["stats"].append(f"Total Licensed Beds: {beds}")

    ownership = row.get("Hospital Ownership")
    if ownership:
        highlights["stats"].append(f"Ownership: {ownership}")

    location = f"{row.get('City')}, {row.get('State')}"
    highlights["stats"].append(f"Location: {location}")

    # Extra stats
    for stat_key in ["ER Wait Time", "Specialties", "Annual Patient Volume"]:
        if row.get(stat_key):
            highlights["stats"].append(f"{stat_key}: {row[stat_key]}")

    return highlights

# -----------------------
# Streamlit App
# -----------------------
st.set_page_config(page_title="Org Profiler", layout="wide")
st.title("🏥 Patient Access Org Profiler — Enhanced Test Mode")

org_name_input = st.text_input("Enter Hospital or Vendor Name", "")

df_cms = load_cms_data_sim()

if org_name_input:
    # Fuzzy matching to find closest name
    names_list = df_cms["Hospital Name"].tolist()
    match_name, score, idx = process.extractOne(
        org_name_input, names_list, scorer=fuzz.WRatio, score_cutoff=50
    ) or (None, 0, None)

    if match_name:
        st.success(f"Matched to: {match_name} ({score}% similarity)")
        row = df_cms.iloc[idx].to_dict()
    else:
        st.warning("No close match found. Showing first entry for preview.")
        row = df_cms.iloc[0].to_dict()

    # Facility Info
    st.subheader("🏥 Facility Information")
    st.json(row)

    # News
    st.subheader("📰 Recent News")
    news_items = get_news_sim(row["Hospital Name"])
    for article in news_items:
        st.markdown(f"- [{article['title']}]({article['link']}) ({article['date']})")

    # Reviews
    st.subheader("💬 Patient & Vendor Reviews")
    reviews = get_reviews_sim(row["Hospital Name"])
    for rev in reviews:
        st.markdown(f"- **{rev['source']}**: {rev['text']}")

    # Highlights & Stats
    st.subheader("⚡ Highlights & Stats")
    highlights = assess_highlights(row)
    st.markdown("**Positives:**")
    for p in highlights["positives"]:
        st.write(f"- {p}")
    st.markdown("**Negatives / Challenges:**")
    for n in highlights["negatives"]:
        st.write(f"- {n}")
    st.markdown("**Key Stats:**")
    for s in highlights["stats"]:
        st.write(f"- {s}")

    # Summary
    st.subheader("📝 Summary")
    summary_text = f"""
**Summary for {row['Hospital Name']}**

{', '.join(highlights['positives'])}  
{', '.join(highlights['negatives'])}  
Located in {row['City']}, {row['State']}, with {row['Total Licensed Beds']} beds. Ownership: {row['Hospital Ownership']}.
"""
    st.write(summary_text)

    # Download JSON
    dossier = {
        "facility_info": row,
        "news": news_items,
        "reviews": reviews,
        "highlights": highlights,
        "summary": summary_text,
        "generated_at": datetime.now().isoformat()
    }
    st.download_button(
        label="📥 Download JSON Report",
        data=json.dumps(dossier, indent=2),
        file_name=f"{org_name_input.replace(' ','_')}_profile.json",
        mime="application/json"
    )
