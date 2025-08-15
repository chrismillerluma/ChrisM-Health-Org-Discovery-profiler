import requests

def fetch_hcahps_data(hospital_id):
    url = f"https://data.cms.gov/provider-data/api/1/datastore/query/hospitals/{hospital_id}/hcahps"
    try:
        response = requests.get(url)
        data = response.json()
        # Extract relevant information
        hcahps_scores = {
            "overall_rating": data.get("overall_rating"),
            "recommendation": data.get("recommendation"),
            # Add other relevant fields
        }
        return hcahps_scores
    except Exception as e:
        return {"error": f"Failed to fetch HCAHPS data: {e}"}
