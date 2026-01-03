import re
import logging
import nltk
from wordfreq import zipf_frequency
from aksharamukha import transliterate

import config
import resource_loader
import nlp_engine
import translator_service
from translator_service import get_indictrans_batch_processor, translate_texts_indictrans2, get_indictrans2_model

# Load resources
# resource_loader is already initialized on import, but we can re-ensure it
# resource_loader.load_data() 

def is_keep_word(word, tag, index, formality_threshold=7):
    # Normalize
    word_low = word.lower()
    
    if not word.strip(): return False
    
    # Rule -1: Structural contractions
    CONTRACTIONS = {"n't", "'s", "'m", "'re", "'ll", "'ve", "'d", "nt"}
    if word_low in CONTRACTIONS or word_low.endswith("n't"): return False
    
    # Rule 0.5: Tech Terms
    if word_low in resource_loader.TECH_TERMS: return True

    # Rule 0.6: Manual Whitelist
    if word_low in resource_loader.MANUAL_KEEP_WORDS: return True

    # Rule 0.7: Verbs (unless whitelisted)
    if tag and tag.startswith('VB'):
         return False
            
    # Rule 1: Formality Score
    if word_low in resource_loader.FORMALITY_SCORES:
        scale = resource_loader.FORMALITY_SCORES[word_low]
        # High threshold (7) -> Keep items >= 3 (Most things)
        if scale >= (10 - formality_threshold):
            return True
        else:
             return False
            
    # Rule 2: Acronyms
    if len(word) > 1 and word.isupper(): return True 
    
    # Rule 3: Proper Nouns
    if len(word) > 1 and word[0].isupper(): 
        if index == 0:
            if tag and tag.startswith('NNP'): return True
        else:
            return True

    # Rule 4: Frequency Fallback
    freq = zipf_frequency(word, 'en')
    if freq < formality_threshold: return True
    
    if tag and tag.startswith('NN'): 
        if freq < (formality_threshold + 1.5): return True
        
    return False

import language_rules

def process_mixed_english(text, formality_threshold=7, target_lang='hi', base_url="http://localhost:5050/translate"):
    logging.info(f"[Mixer] Processing input: {text[:50]}... Lang={target_lang} Threshold={formality_threshold}")
    text = text.replace('“', '"').replace('”', '"').replace('‘', "'").replace('’', "'")
    
    # 1. Tokenize
    words = nlp_engine.tweet_tokenizer.tokenize(text)
    
    # 2. Tagging (using NLP Engine)
    try:
        tagging_text = nlp_engine.normalize_slang(text)
        tagging_text = tagging_text.replace("gonna", "going to").replace("wanna", "want to").replace("gotta", "got to")
        tags_list = nlp_engine.get_pos_tags(tagging_text)
        
        tags = {}
        original_tokens = nltk.word_tokenize(text)
        normalized_tokens = nltk.word_tokenize(tagging_text)
        
        # Simple alignment
        if len(original_tokens) == len(normalized_tokens):
            for orig, (norm, tag) in zip(original_tokens, tags_list):
                tags[orig] = tag
        else:
            tags = dict(nltk.pos_tag(original_tokens))
    except Exception as e:
        logging.error(f"[Mixer] Tagging failed: {e}")
        tags = {}

    # 3. Decision Phase
    kept_words = {}
    masked_words = []
    decisions = []
    clean_words = []
    
    for i, word in enumerate(words):
        clean = re.sub(r'[^\w\s\'-]', '', word)
        clean_words.append(clean)
        tag = tags.get(clean) or tags.get(word)
        decisions.append(is_keep_word(clean, tag, i, formality_threshold))
        
    # Contextual Cohesion (Flip weak words)
    WEAK_TAGS = {'RB', 'RBR', 'RBS', 'IN', 'CC', 'TO', 'DT', 'UH', 'MD'}
    for i in range(len(words)):
        if decisions[i]:
            clean = clean_words[i]
            if clean.lower() in resource_loader.TECH_TERMS: continue
            
            tag = tags.get(clean) or tags.get(words[i])
            if tag and any(tag.startswith(t) for t in WEAK_TAGS):
                left_translated = (i > 0 and not decisions[i-1])
                right_translated = (i < len(words) - 1 and not decisions[i+1])
                if left_translated or right_translated:
                    decisions[i] = False

    # 4. Masking
    is_indictrans = config.get_translation_model() == "indictrans2"
    i = 0
    token_id = 0
    while i < len(words):
        if decisions[i]:
            chunk = [words[i]]
            j = i + 1
            while j < len(words):
                if decisions[j]:
                    chunk.append(words[j])
                    j += 1
                else: break
            
            if is_indictrans:
                token = f"{{{{{token_id}}}}}" 
            else:
                token = f"VAR_{token_id}"
                
            kept_chunk = " ".join(chunk)
            kept_words[token] = kept_chunk
            masked_words.append(token)
            token_id += 1
            i = j
        else:
            masked_words.append(words[i])
            i += 1
            
    masked_text = " ".join(masked_words)
    masked_text = re.sub(r'\s+(n\'t|\'s|\'re|\'ll|\'ve|\'d|\'m)', r'\1', masked_text)
    
    # 5. Translate (Using param target_lang)
    translated_markup = translator_service.translate_batch(masked_text, target_lang, preserve_nouns=False)
    
    # 6. Restoration & Romanization
    if is_indictrans:
        token_pattern = r'\{\{\s*(\d+)\s*\}\}'
    else:
        token_pattern = r'VAR_(\d+)'
    
    parts = re.split(token_pattern, translated_markup, flags=re.IGNORECASE)
    final_parts = []
    is_id_part = False
    
    # Get language specific rules
    script_name = language_rules.get_script_name(target_lang)
    phonetic_map = language_rules.PHONETIC_FIXES.get(target_lang, {})
    protected_suffixes = language_rules.SCHWA_PROTECTION_RULES.get(target_lang, ())
    
    for part in parts:
        if is_id_part:
            if is_indictrans: token_key = f"{{{{{part}}}}}"
            else: token_key = f"VAR_{part}"
            
            original_word = kept_words.get(token_key, f"({part})")
            final_parts.append(original_word)
            is_id_part = False
        else:
            if part.strip():
                # Check safeguards
                has_mask = re.search(r'<\s*m[a]*sk[a]*', part, re.IGNORECASE)
                
                # Check script usage ratio (assuming fallback to Devanagari logic/range for now, but really depends on script)
                # For non-Devanagari, this heuristic might need adjustment, but aksharamukha handles most input 
                # scripts if we tell it the source. But here 'part' is output from translator, so it IS in target_script.
                
                # Basic Romanization Pipeline
                if has_mask:
                     final_parts.append(part)
                else:
                    # Romanize: Target Script -> RomanColloquial
                    # Note: We must specify the Source Script accurately.
                    roman = transliterate.process(script_name, 'RomanColloquial', part)
                    
                    # Apply Phonetic Fixes (Modular)
                    for k, v in phonetic_map.items():
                        roman = roman.replace(k, v)
                    
                    # Schwa Deletion and Cleaning (Conditional)
                    should_schwa_delete = language_rules.is_schwa_deletion_enabled(target_lang)
                    cleaned_roman_words = []
                    
                    for w in roman.split():
                        # Only apply 'a' deletion if language allows it (Indo-Aryan mostly)
                        if should_schwa_delete and len(w) > 3 and w.endswith('a'):
                            is_vowel_pen = w[-2] in 'aeiou'
                            if not is_vowel_pen and not w.endswith(protected_suffixes):
                                w = w[:-1]
                        cleaned_roman_words.append(w)
                    final_parts.append(" ".join(cleaned_roman_words))
            else:
                final_parts.append(part)
            is_id_part = True
            
    # Join with logic to avoid double spacing or missing spaces
    result = "".join(final_parts)
    
    # Simple heuristic to fix spacing issues around English/Indic boundaries
    # If a lowercase char follows a lowercase char directly without space, insert space?
    # Better: Ensure we inserted spaces when appending original_word if needed.
    # The 'part' from `re.split` covers everything *between* matches.
    
    # Re-assemble with simple validation
    # This is tricky because `re.split` gives empty strings for adjacent matches.
    # Let's clean up the list before join.
    
    cleaned_parts = [p for p in final_parts if p]
    
    # "maimmarketkovegetables..." suggests 'maim' (Indic) + 'market' (English) glued.
    # We should ensure spaces around English words if the Indic part didn't have them.
    
    # Actually, the issue is likely that `part` (the translated bit) consumes the spaces
    # or the token replacement doesn't account for surrounding spaces in the original markup.
    
    # For now, let's just ensure we output a clean string.
    # The current `re.split` approach separates TEXT and TOKENS.
    # We should probably join with " " IF the neighbor isn't punctuation?
    
    # Let's try to infer spacing from the original `masked_text` structure? 
    # No, that's gone.
    
    # Fix: Just join with space and then fix double spaces. This is safer for "Mix".
    # BUT, `re.split` returns the text *between* tokens. If tokens were adjacent "VAR_1 VAR_2",
    # the part between is " ". 
    
    # If the translation consumed the space "VAR_1VAR_2" -> part is ""
    # "maim VAR_1ko VAR_2..."
    
    # If we join with empty string, we rely on `part` containing the spaces.
    # If `part` is empty (adjacent tokens), we lose space.
    
    # Let's check if we are adjacent to an ID part.
    
    # Refined Loop Logic (Alternative to simple join)
    output = []
    for i, p in enumerate(final_parts):
        if not p: continue
        # If current is English (ASCII) and prev was Indic (or vice versa), ensure space?
        if output:
            prev = output[-1]
            # If both are words (alphanumeric), ensure space
            if prev[-1].isalnum() and p[0].isalnum():
                output.append(" ")
        output.append(p)
        
    return "".join(output)

COMMON_ENGLISH_WORDS = {
    'hello', 'hi', 'bye', 'goodbye', 'ok', 'okay', 'thanks', 'thank', 'sorry', 
    'please', 'yes', 'no', 'maybe', 'sure', 'cool', 'nice', 'great', 'awesome',
    'wow', 'oh', 'hey', 'hmm', 'yeah', 'yep', 'nope', 'fine', 'good', 'bad',
    'love', 'like', 'hate', 'want', 'need', 'miss', 'happy', 'sad', 'angry',
    'computer', 'phone', 'internet', 'email', 'password', 'app', 'website',
    'video', 'photo', 'music', 'movie', 'game', 'online', 'offline',
}

def process_mixed_english_v2(text, formality_threshold=7, target_lang='hi'):
    if not text or not text.strip():
        return text
    
    logging.info(f"[Mixer V2] Input: {text[:50]}... Lang={target_lang}")
    
    original_words = nltk.word_tokenize(text)
    words_to_restore = {}
    
    for i, word in enumerate(original_words):
        word_low = word.lower()
        if word_low in COMMON_ENGLISH_WORDS:
            words_to_restore[i] = word
        elif word_low in resource_loader.TECH_TERMS:
            words_to_restore[i] = word
        elif len(word) > 1 and word[0].isupper() and i > 0:
            words_to_restore[i] = word
    
    translated = translator_service.translate_batch(text, target_lang, preserve_nouns=False)
    
    script_name = language_rules.get_script_name(target_lang)
    if script_name:
        romanized = transliterate.process(script_name, 'RomanReadable', translated)
    else:
        romanized = translated
    
    romanized_words = nltk.word_tokenize(romanized)
    
    for orig_idx, orig_word in words_to_restore.items():
        if orig_idx < len(romanized_words):
            romanized_words[orig_idx] = orig_word
    
    result = ' '.join(romanized_words)
    result = re.sub(r'\s+([,\.\?\!\;\:])', r'\1', result)
    
    logging.info(f"[Mixer V2] Output: {result[:50]}...")
    return result

def process_batch_mixed_english(texts, threshold=7, target_lang='hi', base_url=None, use_v2=True):
    if not texts:
        return []
    
    is_indictrans = config.get_translation_model() == "indictrans2"
    
    if use_v2 and is_indictrans:
        logging.info(f"[Mixer V2 Batch] Processing {len(texts)} texts with batch inference")
        
        translations = translate_texts_indictrans2(texts, target_lang=target_lang)
        
        results = []
        script_name = language_rules.get_script_name(target_lang)
        
        for i, (orig_text, translated) in enumerate(zip(texts, translations)):
            if script_name:
                romanized = transliterate.process(script_name, 'RomanReadable', translated)
            else:
                romanized = translated
            
            orig_words = nltk.word_tokenize(orig_text)
            rom_words = nltk.word_tokenize(romanized)
            
            for j, word in enumerate(orig_words):
                word_low = word.lower()
                if word_low in COMMON_ENGLISH_WORDS or word_low in resource_loader.TECH_TERMS:
                    if j < len(rom_words):
                        rom_words[j] = word
            
            result = ' '.join(rom_words)
            result = re.sub(r'\s+([,\.\?\!\;\:])', r'\1', result)
            results.append(result)
        
        return results
    else:
        return [process_mixed_english(t, threshold, target_lang, base_url) for t in texts]
