import re
import logging
import nltk
from nltk.tokenize import TweetTokenizer

# 1. Initialize Tokenizer
# reduce_len=True: 'waaaay' -> 'waay'
# preserve_case=True: 'Gonna' -> 'Gonna'
tweet_tokenizer = TweetTokenizer(preserve_case=True, reduce_len=True, strip_handles=False)

# 2. Lazy Load SpaCy
_spacy_nlp = None
def get_spacy_nlp():
    """Lazy load spaCy model"""
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
            logging.info("[spaCy] Loaded en_core_web_sm model")
        except Exception as e:
            logging.warning(f"[spaCy] Failed to load: {e}. Falling back to NLTK.")
            _spacy_nlp = False  # Mark as failed
    return _spacy_nlp if _spacy_nlp else None

# 3. Slang Normalization
SLANG_MAP = {
    # Pronouns & Contractions
    "u": "you", "ur": "your", "ure": "you're", "youre": "you're",
    "im": "i'm", "ive": "i've", "id": "i'd", "ill": "i'll",
    "hes": "he's", "shes": "she's", "theyre": "they're",
    "wont": "won't", "dont": "don't", "cant": "can't", "shouldnt": "shouldn't",
    
    # Common Abbreviations
    "pls": "please", "plz": "please", "thx": "thanks", "thks": "thanks",
    "tbh": "to be honest", "btw": "by the way", "rn": "right now",
    "omg": "oh my god", "nvm": "never mind", "idk": "i don't know",
    "imo": "in my opinion", "imho": "in my honest opinion",
    
    # Verbs & Slang
    "wanna": "want to", "gonna": "going to", "gotta": "got to",
    "tryna": "trying to", "kinda": "kind of", "sorta": "sort of",
    "gimme": "give me", "lemme": "let me", "dunno": "don't know",
    
    # Intensifiers
    "v": "very", "rly": "really", "srsly": "seriously",
    
    # Questions
    "y": "why", "bc": "because", "cuz": "because", "coz": "because",
    "r": "are", "wat": "what", "wen": "when",
}

def normalize_slang(text):
    """Expand chat slang before POS tagging to improve accuracy."""
    words = text.split()
    normalized = []
    for word in words:
        lower = word.lower()
        clean = re.sub(r'[^\w]', '', lower)
        if clean in SLANG_MAP:
            replacement = SLANG_MAP[clean]
            if word[0].isupper() and len(word) > 0:
                replacement = replacement.capitalize()
            normalized.append(replacement)
        else:
            normalized.append(word)
    return " ".join(normalized)

# 4. POS Tagging
def get_pos_tags(text):
    """Ensemble POS tagger: Uses BOTH NLTK + spaCy with majority voting"""
    nlp = get_spacy_nlp()
    
    if not nlp:
        # If no spaCy, fallback to NLTK immediately
        tokens = nltk.word_tokenize(text)
        return nltk.pos_tag(tokens)

    # Run both taggers
    doc = nlp(text)
    spacy_results = [(token.text, token.tag_, token.pos_) for token in doc]
    
    nltk_tokens = nltk.word_tokenize(text)
    nltk_results = nltk.pos_tag(nltk_tokens)
    
    final_tags = []
    
    for i, (word, spacy_tag, spacy_pos) in enumerate(spacy_results):
        if i >= len(nltk_results):
            final_tags.append((word, spacy_tag))
            continue
        
        nltk_word, nltk_tag = nltk_results[i]
        
        # Voting rules
        if spacy_tag == nltk_tag:
            final_tag = spacy_tag
        elif i == 0:
            final_tag = spacy_tag
        elif (spacy_tag.startswith('NNP') or nltk_tag.startswith('NNP')) or \
             (spacy_tag.startswith('VB') or nltk_tag.startswith('VB')):
            # Prioritize spaCy for critical tags
            final_tag = spacy_tag
        else:
            final_tag = spacy_tag
        
        final_tags.append((word, final_tag))
    
    return final_tags

# 5. Noun Extraction
def extract_and_mask_nouns(text):
    """Extract proper nouns and acronyms, mask with placeholders."""
    nlp = get_spacy_nlp()
    
    if nlp:
        doc = nlp(text)
        noun_map = {}
        masked_tokens = []
        placeholder_id = 0
        
        for token in doc:
            should_preserve = False
            # Rule 1: Acronyms
            if len(token.text) > 1 and token.text.isupper() and token.text.isalpha():
                should_preserve = True
            # Rule 2: Proper Nouns
            elif token.pos_ == "PROPN":
                should_preserve = True
            
            if should_preserve:
                placeholder = f"NOUN_{placeholder_id}"
                noun_map[placeholder] = token.text
                masked_tokens.append(placeholder)
                placeholder_id += 1
            else:
                masked_tokens.append(token.text)
        
        masked_text = ""
        for i, token in enumerate(doc):
            if i > 0 and not token.is_punct and token.text not in ["'", "'s"]:
                masked_text += " "
            masked_text += masked_tokens[i]

    else:
        # Fallback NLTK logic
        tokens = nltk.word_tokenize(text)
        tags = nltk.pos_tag(tokens)
        noun_map = {}
        masked_tokens = []
        placeholder_id = 0
        
        for i, (word, tag) in enumerate(tags):
            should_preserve = False
            if len(word) > 1 and word.isupper() and word.isalpha():
                should_preserve = True
            elif tag in ('NNP', 'NNPS'):
                should_preserve = True
            
            if should_preserve:
                placeholder = f"NOUN_{placeholder_id}"
                noun_map[placeholder] = word
                masked_tokens.append(placeholder)
                placeholder_id += 1
            else:
                masked_tokens.append(word)
        
        masked_text = ' '.join(masked_tokens)
        masked_text = re.sub(r'\s+([.,!?;:])', r'\1', masked_text)
    
    return masked_text, noun_map

def restore_nouns(translated_text, noun_map):
    """Restore nouns from placeholders."""
    result = translated_text
    for placeholder, original in noun_map.items():
        result = re.sub(r'\b' + re.escape(placeholder) + r'\b', original, result)
    return result

def ensure_nltk():
    """Ensure required NLTK data is downloaded."""
    try:
        nltk.pos_tag(['test'])
    except LookupError:
        nltk.download('punkt')
        nltk.download('punkt_tab')
        nltk.download('averaged_perceptron_tagger')
        nltk.download('averaged_perceptron_tagger_eng')

# Auto-run ensure
ensure_nltk()
