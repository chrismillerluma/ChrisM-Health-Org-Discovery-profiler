def get_healthgrades_reviews(org_name, max_items=5):
    """
    Scrape Healthgrades for reviews and ratings.
    """
    query = f"{org_name} site:healthgrades.com"
    url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    headers = {"User-Agent": "Mozilla/5.0"}
    reviews = []
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        # Approximate review snippets
        snippets = soup.find_all("span")
        for s in snippets:
            text = s.get_text()
            if len(text) > 50 and len(reviews) < max_items:
                reviews.append(text)
    except:
        pass
    return reviews

def analyze_sentiment(review_text):
    """
    Simple heuristic sentiment labeling.
    """
    positive_words = ["excellent", "great", "good", "friendly", "helpful", "best", "professional"]
    negative_words = ["poor", "bad", "terrible", "rude", "long wait", "problem"]
    score = 0
    for w in positive_words:
        score += review_text.lower().count(w)
    for w in negative_words:
        score -= review_text.lower().count(w)
    return "Positive" if score > 0 else "Negative" if score < 0 else "Neutral"

def get_structured_reviews(org_name):
    """
    Combine Healthgrades, Yelp, and Google snippets into structured data with sentiment.
    """
    reviews = []
    for r in get_healthgrades_reviews(org_name, max_items=5):
        reviews.append({"source": "Healthgrades", "text": r, "sentiment": analyze_sentiment(r)})
    # Add Yelp scraping similarly if desired
    return reviews
