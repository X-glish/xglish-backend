import logging
import config
from libretranslate.language import load_languages
import nlp_engine
import time
import threading
import queue

# IndicTrans2 lazy loading
_indictrans_model = None
_indictrans_tokenizer = None
_indictrans_processor = None
_indictrans_loaded_model_name = None

def get_indictrans2_model():
    """Lazy load IndicTrans2 model."""
    global _indictrans_model, _indictrans_tokenizer, _indictrans_processor, _indictrans_loaded_model_name
    
    cfg = config.load_config()
    target_model_name = cfg.get("indictrans_model", "ai4bharat/indictrans2-en-indic-dist-200M")

    if _indictrans_model is not None and _indictrans_loaded_model_name == target_model_name:
        return _indictrans_model, _indictrans_tokenizer, _indictrans_processor
    
    if _indictrans_model is not None:
        logging.info(f"[IndicTrans2] Switching model from {_indictrans_loaded_model_name} to {target_model_name}...")
        _indictrans_model = None

    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        from IndicTransToolkit.processor import IndicProcessor
        
        hf_token = config.get_hf_token()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logging.info(f"[IndicTrans2] Loading model {target_model_name} on {device}...")
        
        _indictrans_tokenizer = AutoTokenizer.from_pretrained(target_model_name, trust_remote_code=True, token=hf_token or None)
        _indictrans_model = AutoModelForSeq2SeqLM.from_pretrained(target_model_name, trust_remote_code=True, dtype=torch.float32, token=hf_token or None).to(device)
        _indictrans_processor = IndicProcessor(inference=True)
        
        logging.info(f"[IndicTrans2] Model loaded: {target_model_name}")
        _indictrans_loaded_model_name = target_model_name
        return _indictrans_model, _indictrans_tokenizer, _indictrans_processor
    except Exception as e:
        logging.error(f"[IndicTrans2] Failed to load model: {e}")
        raise

def translate_batch_libretranslate(text, target_lang, preserve_nouns=True):
    """LibreTranslate translation."""
    if not text or not text.strip(): return text
    try:
        noun_map = {}
        if preserve_nouns:
            masked_text, noun_map = nlp_engine.extract_and_mask_nouns(text)
        else:
            masked_text = text
        
        languages = load_languages()
        lang_map = {l.code: l for l in languages}
        src_lang = lang_map.get('en')
        tgt_lang = lang_map.get(target_lang)
        
        if not src_lang or not tgt_lang: return text
        translator = src_lang.get_translation(tgt_lang)
        if not translator: return text
        
        translated = translator.translate(masked_text)
        
        if preserve_nouns and noun_map:
            translated = nlp_engine.restore_nouns(translated, noun_map)
        
        return translated
    except Exception as e:
        logging.error(f"[LibreTranslate] Error: {e}")
        return text

# ISO to IndicTrans2 FLORES-200 Code Mapping
ISO_TO_INDICTRANS2 = {
    'hi': 'hin_Deva',
    'en': 'eng_Latn',
    'bn': 'ben_Beng',
    'ta': 'tam_Taml',
    'te': 'tel_Telu',
    'mr': 'mar_Deva',
    'gu': 'guj_Gujr',
    'kn': 'kan_Knda',
    'ml': 'mal_Mlym',
    'pa': 'pan_Guru',
    'or': 'ory_Orya',
    'as': 'asm_Beng',
    'ur': 'urd_Arab',
    'sa': 'san_Deva',
    'ne': 'npi_Deva',
    'sd': 'snd_Arab', # Sindhi
    'ks': 'kas_Arab', # Kashmiri
    'gom': 'gom_Deva', # Konkani
    'mai': 'mai_Deva', # Maithili
    'doi': 'doi_Deva', # Dogri
    'brx': 'brx_Deva', # Bodo
    'mni': 'mni_Beng', # Manipuri
}

def translate_batch_indictrans2(text, target_lang='hi', preserve_nouns=True):
    """IndicTrans2 translation."""
    if not text or not text.strip(): return text
    try:
        import torch
        model, tokenizer, processor = get_indictrans2_model()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        noun_map = {}
        if preserve_nouns:
            masked_text, noun_map = nlp_engine.extract_and_mask_nouns(text)
        else:
            masked_text = text
        
        tgt_lang_code = ISO_TO_INDICTRANS2.get(target_lang, 'hin_Deva')
        
        batch = processor.preprocess_batch([masked_text], src_lang="eng_Latn", tgt_lang=tgt_lang_code)
        inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True).to(device)
        
        with torch.no_grad():
            generated = model.generate(**inputs, use_cache=False, min_length=0, max_length=256, num_beams=5)
        
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        translations = processor.postprocess_batch(decoded, lang=tgt_lang_code)
        translated = translations[0]
        
        if preserve_nouns and noun_map:
            translated = nlp_engine.restore_nouns(translated, noun_map)
        
        return translated
    except Exception as e:
        logging.error(f"[IndicTrans2] Error: {e}. Fallback to LibreTranslate.")
        return translate_batch_libretranslate(text, target_lang, preserve_nouns=preserve_nouns)

def translate_texts_indictrans2(texts, target_lang='hi'):
    """Bulk translate a list of texts in a single GPU call."""
    if not texts: return []
    texts = [t if t and t.strip() else "" for t in texts]
    
    try:
        import torch
        model, tokenizer, processor = get_indictrans2_model()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        tgt_lang_code = ISO_TO_INDICTRANS2.get(target_lang, 'hin_Deva')
        
        logging.info(f"[IndicTrans2 Bulk] Processing {len(texts)} texts. Target: {tgt_lang_code}")
        
        batch = processor.preprocess_batch(texts, src_lang="eng_Latn", tgt_lang=tgt_lang_code)
        inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt", return_attention_mask=True).to(device)
        
        with torch.no_grad():
            generated = model.generate(**inputs, use_cache=False, min_length=0, max_length=256, num_beams=5)
        
        decoded = tokenizer.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        translations = processor.postprocess_batch(decoded, lang=tgt_lang_code)
        return translations
    except Exception as e:
        logging.error(f"[IndicTrans2 Bulk] Error: {e}")
        return texts

def translate_texts_batch(texts, target_lang='hi'):
    """
    Bulk translate a list of texts, strictly respecting the configured model.
    """
    selected_model = config.get_translation_model()
    
    if selected_model == "indictrans2":
        return translate_texts_indictrans2(texts, target_lang=target_lang)
    else:
        # LibreTranslate Fallback (Iterative for now as our wrapper is single-text focused)
        # Note: LibreTranslate local API *does* support batch, but our translate_batch_libretranslate
        # currently handles noun masking per string. 
        logging.info(f"[Translator] Batch processing via LibreTranslate (Iterative) for {len(texts)} items.")
        return [translate_batch_libretranslate(t, target_lang) for t in texts]

def translate_batch(text, target_lang, preserve_nouns=False):
    """Route to selected translation model."""
    selected_model = config.get_translation_model()
    if selected_model == "indictrans2":
        return translate_batch_indictrans2(text, target_lang, preserve_nouns=preserve_nouns)
    else:
        return translate_batch_libretranslate(text, target_lang, preserve_nouns=preserve_nouns)

# --- Batch Processor ---
class IndicTransBatchProcessor:
    def __init__(self, batch_wait_ms=0.05, max_batch_size=32):
        self.queue = queue.Queue()
        self.batch_wait_ms = batch_wait_ms
        self.max_batch_size = max_batch_size
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_queue)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        self.results = {}
        self.lock = threading.Lock()

    def translate(self, text, target_lang='hi'):
        if not text: return ""
        future = threading.Event()
        req_id = id(future)
        self.queue.put((req_id, text, target_lang, future))
        future.wait()
        with self.lock:
            return self.results.pop(req_id, text)

    def _process_queue(self):
        while self.running:
            batch = []
            try:
                # Wait for first item
                item = self.queue.get(timeout=0.1)
                batch.append(item)
                
                # Collect more
                start_wait = time.time()
                while len(batch) < self.max_batch_size and (time.time() - start_wait) < self.batch_wait_ms:
                    try:
                        item = self.queue.get_nowait()
                        batch.append(item)
                    except queue.Empty:
                        break
                        
                # Process batch
                if batch:
                    try:
                        texts = [item[1] for item in batch]
                        # Assume all same lang for now or pick majority? 
                        # Simplification: use first item's lang
                        lang = batch[0][2] 
                        
                        translations = translate_texts_indictrans2(texts, target_lang=lang)
                        
                        with self.lock:
                            for i, (req_id, _, _, future) in enumerate(batch):
                                self.results[req_id] = translations[i] if i < len(translations) else texts[i]
                                future.set()
                    except Exception as e:
                        logging.error(f"Batch processing failed: {e}")
                        # Fallback: Release all with error (or original text)
                        with self.lock:
                            for req_id, orig, _, future in batch:
                                self.results[req_id] = orig
                                future.set()
                                
            except queue.Empty:
                continue

    def shutdown(self):
        self.running = False
        self.worker_thread.join()

_batch_processor = None
def get_indictrans_batch_processor():
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = IndicTransBatchProcessor()
    return _batch_processor
