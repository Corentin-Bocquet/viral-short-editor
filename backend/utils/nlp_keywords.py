"""NLP keyword classification for subtitle coloring."""
from typing import Dict, List
import re


# Color classification dictionaries
RED_KEYWORDS = {
    # Négatif / Danger
    "mort", "mourir", "décès", "peur", "effrayant", "terrorisant",
    "perte", "perdre", "perdu", "dette", "endetté", "dettes",
    "crise", "échec", "échouer", "échoué", "faillite", "ruine",
    "problème", "problèmes", "difficulté", "danger", "dangereux",
    "risque", "risqué", "arnaque", "arnaquer", "piège",
    "mensonge", "mentir", "faux", "catastrophe", "terrible",
    "alerte", "attention", "interdit", "jamais", "éviter",
    "erreur", "faute", "mauvais", "pire", "désastreux",
    "impossible", "difficile", "compliqué", "dur", "souffrir",
    # English equivalents
    "death", "die", "fear", "loss", "lose", "debt",
    "crisis", "fail", "failure", "bankruptcy", "problem",
    "danger", "dangerous", "risk", "scam", "trap", "lie",
    "disaster", "alert", "warning", "never", "avoid", "error",
    "mistake", "bad", "worse", "worst", "impossible", "difficult",
}

GREEN_KEYWORDS = {
    # Positif / Argent / Succès
    "argent", "euros", "euro", "dollar", "dollars", "millionaire",
    "million", "millions", "milliard", "milliards", "richesse",
    "riche", "riches", "fortune", "fortuné", "profit", "profits",
    "gain", "gagner", "gagne", "gagné", "revenus", "revenu",
    "salaire", "investir", "investissement", "business",
    "succès", "réussir", "réussite", "victoire", "gagner",
    "croissance", "opportunité", "opportunités", "chance",
    "liberté", "libre", "indépendant", "indépendance",
    "santé", "bonheur", "heureux", "gratuit", "offre",
    "promotion", "augmentation", "bonus", "bénéfice",
    "rentable", "rentabilité", "performance", "efficace",
    # English equivalents
    "money", "cash", "rich", "wealth", "profit", "gain",
    "earn", "revenue", "income", "salary", "invest", "investment",
    "business", "success", "successful", "win", "winner", "growth",
    "opportunity", "freedom", "free", "health", "happiness",
    "bonus", "benefit", "profitable", "performance", "efficient",
}

YELLOW_KEYWORDS = {
    # Important / Clé / Attention
    "secret", "secrets", "caché", "attention", "important",
    "essentiel", "crucial", "clé", "clés", "unique",
    "exclusif", "exclusivement", "révèle", "révéler",
    "découvre", "découvrir", "découvert", "stratégie",
    "méthode", "technique", "astuce", "astuces", "hack",
    "vrai", "vraiment", "vérité", "réel", "réellement",
    "premier", "première", "dernier", "dernière", "nouveau",
    "nouvelle", "maintenant", "aujourd'hui", "urgent",
    "rapidement", "vite", "immédiat", "choc", "incroyable",
    "surprenant", "étonnant", "jamais", "toujours",
    # English equivalents
    "secret", "hidden", "attention", "important", "essential",
    "crucial", "key", "unique", "exclusive", "reveal",
    "discover", "strategy", "method", "technique", "trick",
    "hack", "true", "truth", "real", "first", "last",
    "new", "now", "today", "urgent", "quickly", "fast",
    "immediate", "shocking", "incredible", "amazing", "never",
}


def normalize_word(word: str) -> str:
    """Normalize word for comparison (lowercase, remove punctuation).
    
    Args:
        word: Input word
        
    Returns:
        Normalized word
    """
    # Remove punctuation and convert to lowercase
    word = re.sub(r'[^\w\s\'à-ÿ]', '', word.lower())
    # Remove common French contractions
    word = word.replace("l'", "").replace("d'", "").replace("qu'", "")
    return word.strip()


def classify_word(word: str) -> str:
    """Classify a word into a color category.
    
    Args:
        word: Word to classify
        
    Returns:
        Color code: 'red', 'green', 'yellow', or 'white'
    """
    normalized = normalize_word(word)
    
    if not normalized:
        return "white"
    
    # Check keywords (order matters: red > green > yellow > white)
    if normalized in RED_KEYWORDS:
        return "red"
    elif normalized in GREEN_KEYWORDS:
        return "green"
    elif normalized in YELLOW_KEYWORDS:
        return "yellow"
    else:
        return "white"


def classify_keywords(text: str) -> Dict[str, str]:
    """Classify all words in text into color categories.
    
    Args:
        text: Input text
        
    Returns:
        Dictionary mapping each word to its color
    """
    # Split text into words
    words = text.split()
    
    result = {}
    for word in words:
        # Keep original word as key but classify normalized version
        color = classify_word(word)
        result[word] = color
    
    return result


def get_emoji_for_text(text: str) -> str:
    """Get relevant emoji based on text content.
    
    Args:
        text: Input text segment
        
    Returns:
        Emoji character or empty string
    """
    text_lower = text.lower()
    
    # Emoji mapping (order matters for priority)
    emoji_map = [
        # Money & Business
        (["argent", "euros", "dollar", "riche", "fortune", "profit", "money", "cash"], "💰"),
        (["business", "entreprise", "startup"], "💼"),
        
        # Growth & Success
        (["croissance", "augment", "monte", "growth", "increase", "up"], "📈"),
        (["succès", "victoire", "gagner", "success", "win", "winner"], "🏆"),
        
        # Thinking & Strategy
        (["cerveau", "intelligence", "stratégie", "brain", "think", "strategy"], "🧠"),
        (["idée", "astuce", "hack", "idea", "trick"], "💡"),
        
        # Time & Urgency
        (["temps", "maintenant", "urgent", "rapide", "time", "now", "fast"], "⏰"),
        (["aujourd'hui", "today"], "📅"),
        
        # Emotions & Reactions
        (["feu", "incroyable", "choc", "fire", "amazing", "shock"], "🔥"),
        (["attention", "alerte", "danger", "warning", "alert"], "⚠️"),
        
        # Positive/Negative
        (["oui", "correct", "bon", "yes", "good", "right"], "✅"),
        (["non", "faux", "éviter", "no", "wrong", "avoid"], "❌"),
        
        # Secrets & Mystery
        (["secret", "caché", "révèle", "hidden", "reveal"], "🤫"),
        
        # Health & Wellness
        (["santé", "fitness", "sport", "health"], "💪"),
        
        # Learning & Knowledge
        (["apprendre", "étude", "éducation", "learn", "study", "education"], "📚"),
    ]
    
    for keywords, emoji in emoji_map:
        if any(keyword in text_lower for keyword in keywords):
            return emoji
    
    return ""  # No emoji found


def should_insert_emoji(segment_index: int, total_segments: int) -> bool:
    """Determine if an emoji should be inserted at this segment.
    
    Args:
        segment_index: Current segment index (0-based)
        total_segments: Total number of segments
        
    Returns:
        True if emoji should be inserted
    """
    # Insert emoji every 4 segments (configurable)
    return segment_index > 0 and segment_index % 4 == 0
