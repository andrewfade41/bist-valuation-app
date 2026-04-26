import feedparser
import re
import urllib.parse
from datetime import datetime

# Turkish Financial Sentiment Lexicon
SENTIMENT_DICT = {
    # Positive keywords
    "yükseliş": 1.0, "rekor": 1.2, "kar": 0.8, "kazanç": 0.8, "artış": 0.6,
    "pozitif": 0.7, "güçlü": 0.8, "büyüme": 0.7, "temettü": 0.5, "anlaşma": 0.9,
    "ihale": 0.9, "beklenti üstü": 1.1, "destek": 0.4, "tavan": 1.5, "alımlar": 0.6,
    "toparlanma": 0.5, "zirve": 0.8, "fırsat": 0.6, "iyileşme": 0.5, "stabil": 0.2,
    "uygun": 0.3, "ucuz": 0.5, "potansiyel": 0.6, "hedef": 0.4, "gelişme": 0.4,
    "onay": 0.7, "yatırım": 0.6, "kap": 0.3, "açıkladı": 0.2, "sıçrama": 1.0,
    
    # Negative keywords
    "düşüş": -1.0, "zarar": -1.2, "kayıp": -1.0, "azalış": -0.6, "negatif": -0.7,
    "zayıf": -0.8, "daralma": -0.7, "iptal": -1.1, "beklenti altı": -1.1, "direnç": -0.4,
    "taban": -1.5, "satış": -0.6, "gerileme": -0.5, "dip": -0.8, "risk": -0.7,
    "uyarı": -0.8, "dava": -0.9, "ceza": -1.0, "enflasyon": -0.4, "faiz artışı": -0.5,
    "belirsizlik": -0.6, "kriz": -1.2, "satıcı": -0.4, "baskı": -0.5, "panik": -1.0,
    "erime": -0.8, "volatilit": -0.3, "jeopolitik": -0.5, "engelleme": -0.6
}

def clean_text(text):
    """Simple text cleaning for sentiment analysis."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def score_headline(headline):
    """Scores a single headline based on the sentiment dictionary."""
    cleaned = clean_text(headline)
    score = 0
    words = cleaned.split()
    
    # Check for multi-word phrases first (e.g., 'beklenti üstü')
    for phrase, p_score in SENTIMENT_DICT.items():
        if " " in phrase and phrase in cleaned:
            score += p_score
            # Remove phrase to avoid double counting single words
            cleaned = cleaned.replace(phrase, "")
            
    # Check single words
    words = cleaned.split()
    found_words = []
    for word in words:
        if word in SENTIMENT_DICT:
            score += SENTIMENT_DICT[word]
            found_words.append(word)
            
    return score, found_words

def fetch_stock_news(ticker, limit=10):
    """
    Fetches the latest news for a ticker from Google News RSS.
    Returns a list of news dictionaries.
    """
    # Use ticker + 'hisse' for better Turkish results
    query = f"{ticker} hisse"
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=tr&gl=TR&ceid=TR:tr"
    
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        
        for entry in feed.entries[:limit]:
            title = entry.title
            # Google News titles usually follow "Headline - Source" format
            source = "Bilinmiyor"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                headline = parts[0]
                source = parts[1]
            else:
                headline = title
                
            score, keywords = score_headline(headline)
            
            news_items.append({
                "title": headline,
                "source": source,
                "link": entry.link,
                "published": entry.published if hasattr(entry, 'published') else "Tarih Belirsiz",
                "score": score,
                "keywords": keywords,
                "sentiment": "Pozitif" if score > 0 else ("Negatif" if score < 0 else "Nötr")
            })
            
        return news_items
    except Exception as e:
        print(f"Error fetching news for {ticker}: {e}")
        return []

def get_overall_sentiment(news_items):
    """Calculates overall sentiment metrics from a list of news items."""
    if not news_items:
        return 50, "Veri Yok", "neutral"
    
    total_score = sum(item['score'] for item in news_items)
    avg_score = total_score / len(news_items)
    
    # Normalize score to 0-100 scale (0: extreme negative, 50: neutral, 100: extreme positive)
    # We assume a score of 1.0 per headline is "strong". 
    # With 10 headlines, a total score of 5 or more is very bullish.
    normalized = 50 + (avg_score * 50)
    normalized = max(0, min(100, normalized))
    
    if normalized > 65:
        summary = "Boğa (Bullish) - Haber akışı pozitif."
        css_class = "bullish"
    elif normalized < 35:
        summary = "Ayı (Bearish) - Haber akışı negatif."
        css_class = "bearish"
    else:
        summary = "Nötr - Dengeli haber akışı."
        css_class = "neutral"
        
    return round(normalized, 1), summary, css_class

if __name__ == "__main__":
    # Test
    ticker = "THYAO"
    news = fetch_stock_news(ticker)
    score, summary, _ = get_overall_sentiment(news)
    print(f"Sentiment for {ticker}: {score}/100 - {summary}")
    for item in news[:3]:
        print(f"- {item['title']} ({item['sentiment']})")
