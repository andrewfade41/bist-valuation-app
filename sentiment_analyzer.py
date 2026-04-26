import feedparser
import re
import urllib.parse
from datetime import datetime

# Authority Financial Sources
AUTHORITY_SITES = [
    "investing.com",
    "bloomberght.com",
    "borsagundem.com",
    "foreks.com",
    "ekonomist.com.tr",
    "dunya.com",
    "bigpara.hurriyet.com.tr",
    "kap.org.tr"
]

# Turkish Financial Sentiment Lexicon
SENTIMENT_DICT = {
    # Positive keywords
    "yükseliş": 1.0, "rekor": 1.2, "kar": 0.8, "kazanç": 0.8, "artış": 0.6,
    "pozitif": 0.7, "güçlü": 0.8, "büyüme": 0.7, "temettü": 0.5, "anlaşma": 0.9,
    "ihale": 0.9, "beklenti üstü": 1.1, "destek": 0.4, "tavan": 1.5, "alımlar": 0.6,
    "toparlanma": 0.5, "zirve": 0.8, "fırsat": 0.6, "iyileşme": 0.5, "stabil": 0.2,
    "uygun": 0.3, "ucuz": 0.5, "potansiyel": 0.6, "hedef": 0.4, "gelişme": 0.4,
    "onay": 0.7, "yatırım": 0.6, "kap": 0.3, "açıkladı": 0.2, "sıçrama": 1.0,
    "revize": 0.3, "alım": 0.4, "iyimser": 0.5, "beklenti": 0.2,
    
    # Negative keywords
    "düşüş": -1.0, "zarar": -1.2, "kayıp": -1.0, "azalış": -0.6, "negatif": -0.7,
    "zayıf": -0.8, "daralma": -0.7, "iptal": -1.1, "beklenti altı": -1.1, "direnç": -0.4,
    "taban": -1.5, "satış": -0.6, "gerileme": -0.5, "dip": -0.8, "risk": -0.7,
    "uyarı": -0.8, "dava": -0.9, "ceza": -1.0, "enflasyon": -0.4, "faiz artışı": -0.5,
    "belirsizlik": -0.6, "kriz": -1.2, "satıcı": -0.4, "baskı": -0.5, "panik": -1.0,
    "erime": -0.8, "volatilit": -0.3, "jeopolitik": -0.5, "engelleme": -0.6,
    "karamsar": -0.5, "kısıtlama": -0.6
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
    
    # Check for multi-word phrases first (e.g., 'beklenti üstü')
    for phrase, p_score in SENTIMENT_DICT.items():
        if " " in phrase and phrase in cleaned:
            score += p_score
            cleaned = cleaned.replace(phrase, "")
            
    # Check single words
    words = cleaned.split()
    found_words = []
    for word in words:
        if word in SENTIMENT_DICT:
            score += SENTIMENT_DICT[word]
            found_words.append(word)
            
    return score, found_words

def fetch_rss_feed(query, limit=10):
    """Internal helper to fetch news from a specific query."""
    # Add 'when:1y' to filter news from the last year
    query_with_time = f"{query} when:1y"
    encoded_query = urllib.parse.quote(query_with_time)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=tr&gl=TR&ceid=TR:tr"
    
    items = []
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries[:limit]:
            title = entry.title
            source = "Bilinmiyor"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                headline = parts[0]
                source = parts[1]
            else:
                headline = title
                
            score, keywords = score_headline(headline)
            
            # Check if it's an authority site
            is_authority = any(site in entry.link.lower() for site in AUTHORITY_SITES)
            
            items.append({
                "title": headline,
                "source": source,
                "link": entry.link,
                "published": entry.published if hasattr(entry, 'published') else "Tarih Belirsiz",
                "score": score,
                "keywords": keywords,
                "is_authority": is_authority,
                "sentiment": "Pozitif" if score > 0 else ("Negatif" if score < 0 else "Nötr")
            })
    except Exception:
        pass
    return items

def fetch_stock_news(ticker, limit=15):
    """
    Fetches the latest news for a ticker with high-signal source filtering.
    """
    # 1. General search
    general_news = fetch_rss_feed(f"{ticker} hisse", limit=10)
    
    # 2. Authority specific search
    authority_query = f"{ticker} ({' OR '.join(['site:' + s for s in AUTHORITY_SITES])})"
    authority_news = fetch_rss_feed(authority_query, limit=10)
    
    # Merge and deduplicate
    all_news = authority_news + general_news
    unique_news = []
    seen_links = set()
    
    for item in all_news:
        if item['link'] not in seen_links:
            unique_news.append(item)
            seen_links.add(item['link'])
            
    # Sort by published date (newest first) - simple string sort is often enough for RSS formats
    unique_news.sort(key=lambda x: x['published'], reverse=True)
    
    return unique_news[:limit]

def get_overall_sentiment(news_items):
    """Calculates overall sentiment metrics with authority weighting."""
    if not news_items:
        return 50, "Veri Yok", "neutral"
    
    weighted_scores = []
    for item in news_items:
        score = item['score']
        # Give 1.5x weight to authority sources
        weight = 1.5 if item['is_authority'] else 1.0
        weighted_scores.append(score * weight)
        
    avg_score = sum(weighted_scores) / len(weighted_scores)
    
    # Normalize score to 0-100 scale
    normalized = 50 + (avg_score * 45) # Slightly lower sensitivity to avoid extreme spikes
    normalized = max(0, min(100, normalized))
    
    if normalized > 60:
        summary = "Boğa (Bullish) - Pozitif haber akışı hakim."
        css_class = "bullish"
    elif normalized < 40:
        summary = "Ayı (Bearish) - Negatif haber akışı baskın."
        css_class = "bearish"
    else:
        summary = "Nötr - Haber akışı dengeli."
        css_class = "neutral"
        
    return round(normalized, 1), summary, css_class

if __name__ == "__main__":
    ticker = "THYAO"
    news = fetch_stock_news(ticker)
    score, summary, _ = get_overall_sentiment(news)
    print(f"Enhanced Sentiment for {ticker}: {score}/100 - {summary}")
    for item in news[:5]:
        auth_tag = "[AUTHORITY] " if item['is_authority'] else ""
        print(f"- {auth_tag}{item['title']} ({item['sentiment']})")
