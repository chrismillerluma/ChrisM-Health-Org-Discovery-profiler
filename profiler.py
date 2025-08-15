with st.spinner("Calculating Business Performance / Reputation Score..."):
    try:
        if place_info:
            rating = place_info.get("rating", 0)
            total_reviews = place_info.get("user_ratings_total", 1)
            rep_score = round(rating * min(total_reviews / 100, 1) * 20, 2)
            st.subheader("Business Performance / Reputation Score")
            st.markdown(f"- **Score (0-20)**: {rep_score}")
            st.markdown(f"- **Rating**: {rating} / 5")
            st.markdown(f"- **Total Reviews**: {total_reviews}")
        else:
            st.info("Google Places API key required to calculate reputation score.")
    except Exception as e:
        st.warning(f"Could not calculate performance score: {e}")

# -------------------------
# Download Full Profile
# -------------------------
profile_data = {
    "org_input": org,
    "matched_name": match.get("Hospital Name") or match.to_dict(),
    "news": news,
    "reviews": revs,
    "business_profile": place_info,
    "about_info": about_data,
    "timestamp": datetime.utcnow().isoformat()
}

st.subheader("Download Full Profile")
# JSON
json_bytes = json.dumps(profile_data, indent=2).encode('utf-8')
st.download_button(
    label="Download Full Profile as JSON",
    data=json_bytes,
    file_name=f"{normalize_name(org)}_profile.json",
    mime="application/json"
)
# CSV (reviews only)
if revs:
    df_revs_download = pd.DataFrame(revs)
    csv_bytes = df_revs_download.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Download Reviews as CSV",
        data=csv_bytes,
        file_name=f"{normalize_name(org)}_reviews.csv",
        mime="text/csv"
    )
