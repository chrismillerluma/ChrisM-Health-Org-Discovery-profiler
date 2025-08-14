import streamlit as st
import pandas as pd
import json
from datetime import datetime

# -----------------------
# Simulated Data for Testing
# -----------------------

def load_cms_data_sim():
    # Sample CMS-like data
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
        },
    ]
    df = pd.DataFrame(data)
    return df

def get_news_sim(org_name):
    # Sample news
    return [
        {"title": f"{org_name} launches new patient portal", "link": "#", "date": "2025-08-01"},
        {"title": f"Patient satisfaction rises at {org_name}", "link": "#", "date": "2025-07-15"},
        {"title": f"{org_name} faces staffing shortage", "link": "#", "date": "2025-06-30"},
    ]

def get_reviews_sim(org_name):
    # Sample reviews
    return [
        {"source": "Google Reviews", "text": "Excellent care and friendly staff."},
        {"source": "Healthgrades", "text": "Long wait times in the ER."},
        {"source": "Yelp", "text": "Clean facilities but difficult parking."},
    ]

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

    return highlights

# -----------------------
# Streamlit App
# -----------------------
st.set_page_config(page_title="Org Profiler", layout="wide")
st.title("🏥 Patient Access Org Profiler — Test Mode")

org_name = st.text_input("Enter Hospital or Vendor Name", "")

df_cms = load_cms_data_sim()

if org_name:
    matches = df_cms[df_cms["Hospital Name"].str.contains(org_name, case=False, na=False)]
    if matches.empty:
        st.warning("No matches found. Showing simulated test data for preview.")
        row = df_cms.iloc[0].to_dict()
    else:
        st.success(f"Found {len(matches)} matches — showing first result.")
        row = matches.iloc[0].to_dict()

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
        file_name=f"{org_name.replace(' ','_')}_profile.json",
        mime="application/json"
    )
