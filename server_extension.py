import sys
from flask import request, jsonify
from libretranslate.app import create_app
from libretranslate.main import get_args
from aksharamukha import transliterate
import logging
import json
import config # Added import

# Reduce LibreTranslate logging noise (Set to INFO for TUI visibility)
logging.getLogger('werkzeug').setLevel(logging.INFO)

class UnifiedServer:
    def __init__(self, load_languages=None, port=5050, debug_logging=False, 
                 threads=4, char_limit=2000, batch_limit=10, translation_cache=True, 
                 mode='dev', translation_model='libretranslate'):
        self.debug_logging = debug_logging
        self.mode = mode
        self.translation_model = translation_model
        self.port = port
        
        if translation_model == 'indictrans2':
            # IndicTrans2: Use plain Flask, no LibreTranslate loading needed
            from flask import Flask
            self.app = Flask(__name__)
            self.args = type('Args', (), {'port': port})()  # Minimal args object
            logging.info(f"Using IndicTrans2 mode - no Argos models needed")
        else:
            # LibreTranslate: Load Argos models as before
            # Configure standard LibreTranslate arguments
            # We simulate the command line args
            self.args = get_args()
            
            if load_languages:
                self.args.load_only = load_languages
            else:
                self.args.load_only = "en"
            
            # AUTO-DOWNLOAD missing language models
            self._ensure_models_downloaded(self.args.load_only)
                 
            self.args.update_models = True 
            self.args.disable_web_ui = True 
            self.args.port = port
            self.args.threads = threads
            self.args.char_limit = char_limit
            self.args.batch_limit = batch_limit
            self.args.translation_cache = translation_cache
            
            # Create the standard LibreTranslate App
            self.app = create_app(self.args)
        
        # Inject our Aksharamukha Route
        self.inject_routes()
    
    def _ensure_models_downloaded(self, load_only_str):
        """Download any missing Argos translation models for requested languages"""
        try:
            from argostranslate import package, translate
            
            requested_langs = [l.strip() for l in load_only_str.split(',')]
            logging.info(f"Checking models for: {requested_langs}")
            
            # Get currently installed packages
            installed = package.get_installed_packages()
            installed_pairs = {(p.from_code, p.to_code) for p in installed}
            
            # Update package index
            package.update_package_index()
            available = package.get_available_packages()
            
            # For each requested language, ensure en->X and X->en exist
            for lang in requested_langs:
                if lang == 'en':
                    continue
                    
                # Check en->lang
                if ('en', lang) not in installed_pairs:
                    pkg = next((p for p in available if p.from_code == 'en' and p.to_code == lang), None)
                    if pkg:
                        logging.info(f"Downloading: en -> {lang}...")
                        package.install_from_path(pkg.download())
                        logging.info(f"  Downloaded en -> {lang}")
                    else:
                        logging.warning(f"No model available for en -> {lang}")
                
                # Check lang->en
                if (lang, 'en') not in installed_pairs:
                    pkg = next((p for p in available if p.from_code == lang and p.to_code == 'en'), None)
                    if pkg:
                        logging.info(f"Downloading: {lang} -> en...")
                        package.install_from_path(pkg.download())
                        logging.info(f"  Downloaded {lang} -> en")
                    else:
                        logging.warning(f"No model available for {lang} -> en")
                        
        except Exception as e:
            logging.error(f"Model download check failed: {e}")
    
    def inject_routes(self):
        @self.app.route('/transliterate', methods=['POST'])
        def transliterate_route():
            try:
                data = request.json
                
                # Log incoming request data (only if debug enabled)
                if self.debug_logging:
                    logging.info("="*40)
                    logging.info(f"[Extension Request] /transliterate")
                    logging.info(f"Headers: {dict(request.headers)}")
                    logging.info(f"Full Payload: {json.dumps(data, indent=2)}")
                    logging.info("="*40)
                
                text = data.get('q', data.get('text', ''))
                source = data.get('source', 'autodetect')
                target = data.get('target', 'ISO')

                if source.lower() == 'auto':
                    source = 'autodetect'

                # --- SMART MIXER LOGIC (supports bulk and single) ---
                # Check for "Mix" pattern (e.g., "Hinglish_Mix", "Benglish_Mix" or just "English_Mix"?)
                # We will support strict "LangName_Mix" or "Mix_LangName"
                
                is_smart_mix = False
                target_lang_code = 'hi' # Default
                
                if target == 'Hinglish_Mix':
                    is_smart_mix = True
                    target_lang_code = 'hi'
                elif target.endswith('_Mix'):
                    is_smart_mix = True
                    lang_name = target.replace('_Mix', '')
                    import language_rules
                    target_lang_code = language_rules.LANG_CODE_MAP.get(lang_name, 'hi')
                
                if is_smart_mix:
                    import xglish_mixer
                    import re
                    threshold = float(data.get('threshold', 7.0))
                    if 'formality_threshold' in data:
                         threshold = float(data.get('formality_threshold'))
                    
                    local_url = f"http://127.0.0.1:{self.args.port}/translate"
                    
                    if isinstance(text, list):
                        logging.info(f"[Smart Mix Bulk] Received {len(text)} texts. Target: {target_lang_code}")
                        results = xglish_mixer.process_batch_mixed_english(text, threshold, target_lang=target_lang_code, base_url=local_url)
                        return jsonify({"results": results, "success": True})
                    
                    # SINGLE MODE: q is a string
                    is_english = bool(re.search(r'[a-zA-Z]', text))
                    if is_english:
                        # For single mode, we can use the batch function with a list of one to get batch speed/v2
                        results = xglish_mixer.process_batch_mixed_english([text], threshold, target_lang=target_lang_code, base_url=local_url)
                        result = results[0] if results else text
                    else:
                        result = text
                    
                    if self.debug_logging:
                        logging.info(f"  Result: {result[:50]}...")
                    return jsonify({"result": result, "success": True})
                # --------------------------------

                # Pipeline Logic
                intermediate_lang = "hi" 
                is_roman_pipeline = False
                
                if target == 'RomanColloquial':
                    is_roman_pipeline = True
                    intermediate_lang = 'hi'
                elif target.startswith('Roman_'):
                    is_roman_pipeline = True
                    intermediate_lang = target.split('_')[1]

                if is_roman_pipeline:
                    # Handle Bulk List Input
                    if isinstance(text, list):
                        try:
                            import translator_service
                            translated_list = translator_service.translate_texts_batch(text, target_lang=intermediate_lang)
                            if translated_list:
                                text = translated_list
                                source = 'autodetect'
                                target = 'RomanReadable'
                        except Exception as e:
                            logging.error(f"Pipeline Batch Error: {e}")

                    # Handle Single String Input
                    elif isinstance(text, str):
                        # Heuristic: If English input
                        if any(ord(c) < 128 for c in text):
                            try:
                                import translator_service
                                translated = translator_service.translate_batch(text, intermediate_lang)
                                if translated:
                                    text = translated
                                    source = 'autodetect' 
                                    target = 'RomanReadable' 
                            except Exception as e:
                                logging.error(f"Pipeline Error: {e}")

                # Final map: if using our custom Roman pipeline tags, 
                # the actual target for Aksharamukha is RomanReadable (or ISO)
                if is_roman_pipeline:
                    target = 'RomanReadable'

                if isinstance(text, list):
                    # Bulk Processing for Aksharamukha
                    results = []
                    for t in text:
                        if t and t.strip():
                            results.append(transliterate.process(source, target, t))
                        else:
                            results.append(t)
                    response_data = {"results": results, "success": True}
                else:
                    # Single Processing
                    result = transliterate.process(source, target, text)
                    response_data = {"result": result, "success": True}
                
                if self.debug_logging:
                    logging.info(f"Sending Response: {json.dumps(response_data)}")
                
                return jsonify(response_data)
            except Exception as e:
                logging.error(f"Server Error: {e}", exc_info=True)
                return jsonify({"error": str(e), "success": False}), 500

        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({"status": "online", "success": True})

        @self.app.route('/xglish/languages', methods=['GET'])
        def get_xglish_languages():
            # Return languages based on model
            if self.translation_model == 'indictrans2':
                # All 22 Indic languages as per ISO_TO_INDICTRANS2 keys (simplified for UI)
                from xglish_ui import INDICTRANS_LANGS
                return jsonify([{"val": l[1], "label": l[0]} for l in INDICTRANS_LANGS])
            
            try:
                from libretranslate.language import load_languages
                loaded = load_languages()
                result = [{"val": lang.code, "label": lang.name} for lang in loaded]
                return jsonify(result)
            except Exception as e:
                logging.error(f"Failed to get languages: {e}")
                return jsonify([])

        @self.app.route('/xglish/config', methods=['POST'])
        def update_xglish_config():
            try:
                data = request.json
                current_config = config.load_config()
                
                # Update allowed fields
                if 'libretranslate_languages' in data:
                    current_config['libretranslate_languages'] = data['libretranslate_languages']
                
                # Save
                config.save_config(current_config)
                return jsonify({"success": True, "message": "Configuration saved. Please restart the server to apply changes."})
            except Exception as e:
                logging.error(f"Config Update Error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500


    def run(self):
        print(f"Starting Xglish Unified Server on port {self.args.port} [Mode: {self.mode.upper()}]...")
        if self.mode == 'prod':
            try:
                from waitress import serve
                print(f"✅ Using Waitress (Production WSGI).")
                serve(self.app, host='0.0.0.0', port=self.args.port, threads=self.args.threads)
            except ImportError:
                print("❌ 'waitress' not found. Installing it via 'pip install waitress' is recommended for production.")
                print("⚠️  Falling back to Flask development server.")
                self.app.run(host='0.0.0.0', port=self.args.port, threaded=True)
        else:
            print(f"⚠️  Using Flask Development Server (Debug Mode compatible). Use --prod for production.")
            # Note: debug=False passed to avoid auto-reloader issues with multi-threading if any
            self.app.run(host='0.0.0.0', port=self.args.port, threaded=True)

# Expose for running directly checking import
if __name__ == "__main__":
    mode = 'dev'
    # Clean sys.argv before they reach LibreTranslate's get_args()
    if '--prod' in sys.argv:
        mode = 'prod'
        sys.argv.remove('--prod')
    elif '--production' in sys.argv:
         mode = 'prod'
         sys.argv.remove('--production')

    # Load Config for Languages
    try:
        cfg = config.load_config()
        # Default fallback if config entry missing but file exists
        langs = cfg.get("libretranslate_languages", ["en"])
        if "en" not in langs:
            langs.append("en")
        load_langs_str = ",".join(langs)
    except Exception as e:
        print(f"Config load failed: {e}, using default languages.")
        load_langs_str = "en"

    server = UnifiedServer(mode=mode, load_languages=load_langs_str)
    server.run()
