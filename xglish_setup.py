import sys
import subprocess
import importlib.util

def check_nltk():
    """Checks and downloads NLTK data."""
    print("[Setup] Checking NLTK data...")
    try:
        import nltk
        required = ['punkt', 'punkt_tab', 'averaged_perceptron_tagger']
        for req in required:
            try:
                nltk.data.find(f'tokenizers/{req}') if 'punkt' in req else nltk.data.find(f'taggers/{req}')
            except LookupError:
                print(f"[Setup] Downloading missing NLTK resource: {req}")
                nltk.download(req, quiet=True)
        print("[Setup] NLTK data ready.")
        return True
    except ImportError:
        print("[Setup] NLTK not installed. Please run: pip install nltk")
        return False
    except Exception as e:
        print(f"[Setup] Error checking NLTK: {e}")
        return False

def check_modules():
    """Checks critical python modules."""
    required = ['flask', 'libretranslate', 'aksharamukha', 'requests']
    missing = []
    for package in required:
        if importlib.util.find_spec(package) is None:
            missing.append(package)
    
    if missing:
        print(f"[Setup] Missing critical modules: {', '.join(missing)}")
        print(f"[Setup] Please run: pip install {' '.join(missing)}")
        return False
    return True

def perform_setup():
    print("--- Xglish Environment Setup ---")
    if not check_modules():
        return False
    if not check_nltk():
        return False
    print("-------------------------------")
    return True
