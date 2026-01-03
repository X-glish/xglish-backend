import json
import os
import logging
import subprocess
from wordfreq import zipf_frequency

# Global resources
FORMALITY_SCORES = {}
MANUAL_KEEP_WORDS = set()
TECH_TERMS = set()

DB_REPO_URL = "https://github.com/X-glish/x-glish-db.git"

def ensure_database():
    """Ensure the x-glish-db is present in the home directory."""
    home_dir = os.path.expanduser("~")
    xglish_dir = os.path.join(home_dir, ".xglish")
    db_path = os.path.join(xglish_dir, "x-glish-db")

    if not os.path.exists(db_path):
        logging.info(f"[Loader] Database not found at {db_path}. Downloading...")
        try:
            os.makedirs(xglish_dir, exist_ok=True)
            subprocess.check_call(["git", "clone", DB_REPO_URL, db_path])
            logging.info("[Loader] Database downloaded successfully.")
        except Exception as e:
            logging.error(f"[Loader] Failed to download database: {e}")
            # Fallback to local if exists (dev mode)
            return None
    
    return db_path

def load_data(base_path=None):
    """
    Load all required resources (Formality scores, Whitelists, Tech terms).
    Args:
        base_path: Optional base directory to look for files.
    """
    global FORMALITY_SCORES, MANUAL_KEEP_WORDS, TECH_TERMS
    
    # Priority:
    # 1. Provided base_path
    # 2. Home directory (~/.xglish/x-glish-db)
    # 3. Local directory (fallback)

    if base_path is None:
        # Try home dir first
        home_db = ensure_database()
        if home_db and os.path.exists(home_db):
            base_path = home_db
        else:
            # Fallback to current dir
            base_path = os.path.dirname(__file__)
    
    logging.info(f"[Loader] Loading resources from: {base_path}")

    # 1. Load Formality Scores
    # Note: Corrected typo 'infornal' -> 'informal' based on actual file listing
    # Checking both just in case
    candidates = ['informalbechmark.json', 'infornalbechmark.json']
    
    for fname in candidates:
        try:
            path = os.path.join(base_path, fname)
            if os.path.exists(path):
                logging.info(f"[Loader] Found benchmark: {fname}")
                with open(path, 'r') as f:
                    data = json.load(f)
                    for item in data.get('wordvalue', []):
                        word = item.get('EnglishWord', '').lower()
                        scale = item.get('scale', 5)
                        FORMALITY_SCORES[word] = scale
                logging.info(f"[Loader] Loaded {len(FORMALITY_SCORES)} words from formality benchmark.")
                break
        except Exception as e:
            logging.error(f"[Loader] Failed to load {fname}: {e}")

    # 2. Load Manual Keep Words Whitelist (xglishwordhindi.json)
    try:
        whitelist_path = os.path.join(base_path, 'xglishwordhindi.json')
        if os.path.exists(whitelist_path):
            with open(whitelist_path, 'r') as f:
                data = json.load(f)
                count = 0
                filtered_count = 0
                for item in data.get('wordvalue', []):
                    # Only add if tobeused is true
                    if item.get('tobeused', False):
                        word = item.get('EnglishWord', '').lower()
                        if word:
                            # FREQUENCY GUARDRAIL: Ignore commonly used English words
                            freq = zipf_frequency(word, 'en')
                            if freq > 6.42:
                                filtered_count += 1
                                continue
                                
                            MANUAL_KEEP_WORDS.add(word)
                            count += 1
            logging.info(f"[Loader] Loaded {count} manual whitelist words. Filtered {filtered_count} common words.")
    except Exception as e:
        logging.error(f"[Loader] Failed to load manual whitelist: {e}")

    # 3. Load Tech Terms (TECH_TERMS.json)
    try:
        tech_path = os.path.join(base_path, 'TECH_TERMS.json')
        if os.path.exists(tech_path):
            with open(tech_path, 'r') as f:
                data = json.load(f)
                count = 0
                for item in data.get('wordvalue', []):
                    word = item.get('EnglishWord', '').lower()
                    if word:
                        TECH_TERMS.add(word)
                        count += 1
            logging.info(f"[Loader] Loaded {count} tech terms.")
    except Exception as e:
        logging.error(f"[Loader] Failed to load tech terms: {e}")

# Initial load
load_data()
