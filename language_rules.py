"""
Language Rules Configuration
Centralized store for language-specific phonetic rules, script codes, and processing directives.
"""

# language_rules.py
# Centralized configuration for 22 Indic Languages + English Mix

# 1. ISO-639-1/2 to Language Name Mapping
LANG_CODE_MAP = {
    'Hindi': 'hi',
    'Bengali': 'bn',
    'Tamil': 'ta',
    'Telugu': 'te',
    'Marathi': 'mr',
    'Gujarati': 'gu',
    'Kannada': 'kn',
    'Malayalam': 'ml',
    'Punjabi': 'pa',
    'Odia': 'or',
    'Assamese': 'as',
    'Urdu': 'ur',
    'Sanskrit': 'sa',
    'Nepali': 'ne',
    'Sindhi': 'sd',
    'Kashmiri': 'ks',
    'Konkani': 'gom',
    'Maithili': 'mai',
    'Dogri': 'doi',
    'Bodo': 'brx',
    'Manipuri': 'mni',
    'Santali': 'sat'
}

# 2. Aksharamukha Script Codes (Target Script for Transliteration)
# Used to convert: English/Indic Input -> Target Script -> Roman
SCRIPT_MAP = {
    'hi': 'Devanagari',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'te': 'Telugu',
    'mr': 'Devanagari',
    'gu': 'Gujarati',
    'kn': 'Kannada',
    'ml': 'Malayalam',
    'pa': 'Gurmukhi',
    'or': 'Oriya',
    'as': 'Assamese',
    'ur': 'Urdu',      # Note: Aksharamukha support for Urdu might be limited to specific mappings
    'sa': 'Devanagari',
    'ne': 'Devanagari',
    'sd': 'Arabic',    # Sindhi uses Arabic script in Pakistan/India often, or Devanagari. Defaulting to Arabic for "Sindhi". 'Sindhi' key in Aksharamukha?
    'ks': 'Arabic',    # Kashmiri is typically written in Perso-Arabic
    'gom': 'Devanagari',
    'mai': 'Devanagari',
    'doi': 'Devanagari',
    'brx': 'Devanagari',
    'mni': 'Bengali',  # Meitei Mayek or Bengali script. Bengali is common fallback.
    'sat': 'OlChiki'   # Ol Chiki is the script for Santali
}

def get_script_name(lang_code):
    """Returns Aksharamukha script name for a given language code."""
    # Special handling for Sindhi/Kashmiri if Aksharamukha assumes Devanagari 
    # but we want Perso-Arabic.
    return SCRIPT_MAP.get(lang_code, 'Devanagari')


# 3. Schwa Deletion Protection (Romanization Polish)
# Indo-Aryan languages (Hindi, Marathi, Gujarati) often delete the final 'a'.
# Dravidian languages (South) and Sanskrit usually KEAP the final 'a'.
# We list suffixes that should NOT be cut even in Schwa-deleting languages.
SCHWA_PROTECTION_RULES = {
    # Indo-Aryan (Schwa Deletion Active)
    'hi': ('na', 'la', 'ta', 'da', 'ga', 'ya', 'ka', 'ra', 'ha', 'ma', 'ja'),
    'mr': ('na', 'la', 'ta', 'da', 'ga', 'ya', 'ka', 'ra', 'ha', 'ma', 'ja'),
    'gu': ('na', 'la', 'ta', 'da', 'ga', 'ya', 'ka'),
    'bn': ('o', 'a'), # Bengali usually ends in 'o' sound, rarely 'a' deletion like Hindi.
    'pa': ('na', 'la', 'ta'),
    'ur': ('ah', 'eh'),
    
    # Dravidian & Others (Schwa Retention - Rules here prevent aggressive cleanup)
    # Ideally, we disable Schwa deletion logic for these in xglish_mixer, 
    # but strictly speaking, adding common endings here protects them if logic runs.
    'ta': ('a', 'i', 'u', 'e', 'o'), 
    'te': ('a', 'i', 'u', 'e', 'o'),
    'kn': ('a', 'i', 'u', 'e', 'o'),
    'ml': ('a', 'i', 'u', 'e', 'o'),
    'sa': ('a', 'i', 'u', 'e', 'o', 'm', 'h'),
}

# 4. Phonetic Fixes (Post-Romanization Cleanup)
# "v" vs "w", "b" vs "v", "ee" vs "i" stylization preferences.
PHONETIC_FIXES = {
    'hi': { 'Phr': 'Fr', 'phr': 'fr', 'Ph': 'F', 'ph': 'f', 'v': 'v', 'w': 'v' },
    'mr': { 'Phr': 'Fr', 'phr': 'fr', 'v': 'v', 'zh': 'jh' }, # Marathi 'jh' vs 'z'
    'bn': { 'v': 'b', 'V': 'B', 'w': 'b', 'a': 'o' }, # 'v' is 'b', 'a' is often 'o' sound
    'or': { 'v': 'b', 'w': 'b', 'a': 'o' },
    'as': { 'v': 'b', 'w': 'b', 'ch': 's' }, # Assamese 'ch' is soft 's'
    'ta': { 'zh': 'l', 'th': 'dh' }, # Colloquial tamil preferences
    'te': { 'th': 'd', 'T': 't' },
    'ml': { 'zh': 'l', 'th': 'd' },
    'ur': { 'q': 'k', 'z': 'j' }, # Simplify Urdu sounds for colloquial mix
    'pa': { 'bh': 'p', 'dh': 't' }, # Tonal language characteristics often simplified
}

def is_schwa_deletion_enabled(lang_code):
    """
    Returns True if the language typically requires Schwa deletion (Inherent 'a' removal).
    Indo-Aryan (North) = True
    Dravidian (South), Sanskrit, NE = False
    """
    NO_SCHWA_DELETION = {
        'ta', 'te', 'kn', 'ml', # Dravidian
        'sa', # Sanskrit
        'ne', # Nepali (often keeps it)
        'as', 'or', 'bn', # Eastern (often O sound, distinct)
        'mni', 'sat'
    }
    return lang_code not in NO_SCHWA_DELETION
