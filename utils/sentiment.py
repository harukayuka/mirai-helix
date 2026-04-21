# utils/sentiment.py - Analisis Sentimen Sederhana untuk Mirai
import re

def analyze_sentiment(text: str) -> str:
    """
    Menganalisis sentimen teks secara sederhana berdasarkan kata kunci.
    Returns: "positif", "negatif", atau "netral"
    """
    text = text.lower()
    
    positif_words = [
        "senang", "bahagia", "baik", "sehat", "terima kasih", "makasih", 
        "mantap", "keren", "bagus", "ceria", "semangat", "cinta", "suka"
    ]
    negatif_words = [
        "sedih", "sakit", "buruk", "kecewa", "marah", "lelah", "capek", 
        "pusing", "stres", "takut", "cemas", "gagal", "benci", "payah"
    ]
    
    pos_score = sum(1 for word in positif_words if word in text)
    neg_score = sum(1 for word in negatif_words if word in text)
    
    if pos_score > neg_score:
        return "positif"
    elif neg_score > pos_score:
        return "negatif"
    else:
        return "netral"

def get_mood_emoji(sentiment: str) -> str:
    mapping = {
        "positif": "😊",
        "negatif": "😔",
        "netral": "😐"
    }
    return mapping.get(sentiment, "🤔")
