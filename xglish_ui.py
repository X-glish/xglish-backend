from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Static, Label, Checkbox, SelectionList, Log, TabbedContent, TabPane, Input, RadioSet, RadioButton
from textual.reactive import reactive
import threading
import logging
from datetime import datetime
import os
import xglish_setup  # Import setup helper
import config  # Config system

# Import Backend
from server_extension import UnifiedServer

class ServerThread(threading.Thread):
    def __init__(self, languages, port, logger_func, debug_logging=False, 
                 threads=4, char_limit=2000, batch_limit=10, translation_cache=True,
                 translation_model='libretranslate'):
        super().__init__()
        self.languages = languages
        self.port = int(port)
        self.logger_func = logger_func
        self.debug_logging = debug_logging
        self.threads = int(threads)
        self.char_limit = int(char_limit)
        self.batch_limit = int(batch_limit)
        self.translation_cache = translation_cache
        self.translation_model = translation_model
        self.server = None
        self.daemon = True

    def run(self):
        try:
            self.logger_func(f"Initializing Server with langs: {self.languages} on Port {self.port}...")
            # Capture stdout/stderr? Flask logs to stderr usually.
            # We will just instantiate.
            self.server = UnifiedServer(
                load_languages=self.languages, 
                port=self.port,
                debug_logging=self.debug_logging,
                threads=self.threads,
                char_limit=self.char_limit,
                batch_limit=self.batch_limit,
                translation_cache=self.translation_cache,
                translation_model=self.translation_model
            )
            self.logger_func(f"Server Initialized. Starting on Port {self.port}...")
            self.server.run()
        except Exception as e:
            self.logger_func(f"Server Crash: {e}")

class XglishApp(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #1a1b26;
    }
    Header {
        background: #7c3aed;
        color: white;
    }
    .status-box {
        border: solid #555;
        background: #222;
        padding: 1;
        margin: 1;
        height: auto;
    }
    .status-indicator {
        width: 100%;
        text-align: center;
        background: #ff5555;
        color: white;
        padding: 1;
        margin-bottom: 1;
        text-style: bold;
    }
    .status-indicator.ready {
        background: #f1fa8c;
        color: black;
    }
    .status-indicator.online {
        background: #50fa7b;
        color: black;
    }
    .control-panel {
        align: center middle;
        height: auto;
        padding: 1;
    }
    Button {
        margin: 1;
        width: 30;
    }
    Log {
        border: solid #666;
        background: #000;
        height: 1fr;
    }
    """

    server_running = reactive(False)
    setup_ready = reactive(False)
    
    LIBRETRANS_LANGS = [
        ("English (Required)", "en", True),
        ("Hindi", "hi", False),
        ("Bengali", "bn", False),
        ("Urdu", "ur", False),
    ]
    
    INDICTRANS_LANGS = [
        ("English (Required)", "en", True),
        ("Hindi", "hi", False),
        ("Bengali", "bn", False),
        ("Tamil", "ta", False),
        ("Telugu", "te", False),
        ("Marathi", "mr", False),
        ("Gujarati", "gu", False),
        ("Kannada", "kn", False),
        ("Malayalam", "ml", False),
        ("Punjabi", "pa", False),
        ("Urdu", "ur", False),
        ("Odia", "or", False),
        ("Assamese", "as", False),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with TabbedContent():
            with TabPane("Dashboard", id="tab-dashboard"):
                yield Container(
                    Static("CHECKING DEPENDENCIES...", id="status-ind", classes="status-indicator"),
                    classes="status-box"
                )
                with Horizontal(classes="control-panel"):
                    yield Button("Start Server", id="btn-start", variant="success", disabled=True)
                    yield Button("Stop Server (Exit)", id="btn-stop", variant="error")
                
                yield Label("Server Logs:")
                yield Log(id="server-log")

            with TabPane("Configuration", id="tab-config"):
                yield Label("Server Port:")
                yield Input(value="5050", placeholder="5050", id="input-port")
                
                yield Label("Performance Settings:")
                yield Checkbox("Enable Caching", id="chk-cache", value=True)
                yield Label("Threads:")
                yield Input(value="4", placeholder="4", id="input-threads")
                yield Label("Char Limit:")
                yield Input(value="5000", placeholder="5000", id="input-char")
                yield Label("Batch Limit:")
                yield Input(value="100", placeholder="100", id="input-batch")
                
                yield Checkbox("Enable Debug Logging", id="checkbox-debug-log", value=True)
                yield Label("Select languages to load (More = Slower Startup)", id="lang-label")
                yield SelectionList[str](
                    *[(parse[0], parse[1], parse[2]) for parse in self.LIBRETRANS_LANGS],
                    id="lang-selection"
                )
                yield Label("✓ All 22 Indic languages supported - no selection needed", id="indictrans-msg")
                yield Label("")
                yield Button("Save Configuration", id="btn-save-config", variant="primary")
                yield Label("", id="config-status")

            with TabPane("Translation Model", id="tab-settings"):
                yield Label("Select Translation Engine:")
                yield RadioSet(
                    RadioButton("LibreTranslate (Fast, works with Hinglish mixer)", id="radio-libretranslate", value=True),
                    RadioButton("IndicTrans2 (Better quality, slower)", id="radio-indictrans2"),
                    id="model-selection"
                )
                yield Label("")
                yield Label("Hugging Face Token (for IndicTrans2):")
                yield Input(placeholder="hf_...", id="input-hf-token", password=True)
                yield Label("")
                yield Button("Save Settings", id="btn-save-settings", variant="primary")
                yield Label("", id="settings-status")

        yield Footer()

    def on_mount(self) -> None:
        self.title = "Xglish Control Center"
        self.log_widget = self.query_one("#server-log", Log)
        self.status_ind = self.query_one("#status-ind", Static)
        self.btn_start = self.query_one("#btn-start", Button)
        
        # Load config settings
        self.load_config_settings()
        
        # Run Setup Check in Thread
        threading.Thread(target=self.run_setup_check, daemon=True).start()

    def load_config_settings(self):
        """Load saved configuration into UI"""
        try:
            cfg = config.load_config()
            
            # Set model selection AND update language list
            model = cfg.get("translation_model", "libretranslate")
            radio_set = self.query_one("#model-selection", RadioSet)
            if model == "indictrans2":
                self.query_one("#radio-indictrans2", RadioButton).value = True
                self.update_language_list(1)
            else:
                self.query_one("#radio-libretranslate", RadioButton).value = True
                self.update_language_list(0)
            
            # Set HF token
            hf_token = cfg.get("hf_token", "")
            token_input = self.query_one("#input-hf-token", Input)
            token_input = self.query_one("#input-hf-token", Input)
            token_input.value = hf_token
            
            # Set saved language selections
            saved_langs = cfg.get("libretranslate_languages", ["en"])
            lang_list = self.query_one("#lang-selection", SelectionList)
            for lang_code in saved_langs:
                lang_list.select(lang_code)

        except Exception as e:
            self.log_widget.write_line(f"Failed to load config: {e}")

    def run_setup_check(self):
        self.log_to_widget("Checking Environment & NLTK Data...")
        # Capturing stdout from setup might be tricky since it uses print
        # We'll just trust it and log our own messages
        
        try:
            # We redirect stdout momentarily or just modify xglish_setup to return bool
            # xglish_setup prints to stdout.
            if xglish_setup.perform_setup():
                self.call_from_thread(self.on_setup_success)
            else:
                self.call_from_thread(self.on_setup_failure)
        except Exception as e:
            self.log_to_widget(f"Setup Error: {e}")

    def on_setup_success(self):
        self.log_widget.write_line("Dependencies OK. NLTK Data Ready.")
        self.status_ind.update("READY TO START")
        self.status_ind.add_class("ready")
        self.btn_start.disabled = False
        self.setup_ready = True
        
    def on_setup_failure(self):
        self.log_widget.write_line("CRITICAL: Dependencies missing. See console.")
        self.status_ind.update("SETUP FAILED")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-start":
            if self.server_running:
                self.log_widget.write_line("Server is already running.")
                return
            
            self.start_server()
            
        elif event.button.id == "btn-stop":
            self.exit()
        
        elif event.button.id == "btn-save-settings":
            self.save_settings()

        elif event.button.id == "btn-save-config":
            self.save_config_tab()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle translation engine selection change - update language list"""
        if event.radio_set.id == "model-selection":
            self.update_language_list(event.index)
    
    def update_language_list(self, model_index: int):
        """Update the language selection list based on chosen translation model"""
        try:
            lang_list = self.query_one("#lang-selection", SelectionList)
            lang_label = self.query_one("#lang-label", Label)
            indictrans_msg = self.query_one("#indictrans-msg", Label)
            
            if model_index == 0:
                # LibreTranslate: show language selection, hide message
                lang_list.display = True
                lang_label.update("Select languages to load (More = Slower Startup)")
                indictrans_msg.display = False
                
                lang_list.clear_options()
                for label, code, selected in self.LIBRETRANS_LANGS:
                    lang_list.add_option((label, code))
                    if selected:
                        lang_list.select(code)
                self.log_widget.write_line("Switched to LibreTranslate: 4 languages available")
            else:
                # IndicTrans2: hide language selection, show message
                lang_list.display = False
                lang_label.update("Language Support:")
                indictrans_msg.display = True
                self.log_widget.write_line("Switched to IndicTrans2: All Indic languages supported")
                
        except Exception as e:
            self.log_widget.write_line(f"Language list update failed: {e}")

    def save_settings(self):
        """Save translation model settings to config"""
        try:
            radio_set = self.query_one("#model-selection", RadioSet)
            token_input = self.query_one("#input-hf-token", Input)
            status_label = self.query_one("#settings-status", Label)
            
            # Determine selected model
            selected_model = "libretranslate" if radio_set.pressed_index == 0 else "indictrans2"
            hf_token = token_input.value.strip()
            
            # Save to config
            cfg = config.load_config()
            cfg["translation_model"] = selected_model
            cfg["hf_token"] = hf_token
            config.save_config(cfg)
            
            status_label.update(f"✓ Saved! Using {selected_model.upper()}")
            self.log_widget.write_line(f"Translation model set to: {selected_model}")
        except Exception as e:
            status_label.update(f"✗ Error: {e}")
            status_label.update(f"✗ Error: {e}")
            self.log_widget.write_line(f"Failed to save settings: {e}")

    def save_config_tab(self):
        """Save configuration tab settings"""
        try:
            # Inputs
            port_val = self.query_one("#input-port", Input).value
            threads_val = self.query_one("#input-threads", Input).value
            char_val = self.query_one("#input-char", Input).value
            batch_val = self.query_one("#input-batch", Input).value
            cache_val = self.query_one("#chk-cache", Checkbox).value
            debug_val = self.query_one("#checkbox-debug-log", Checkbox).value
            
            # Languages
            lang_list = self.query_one("#lang-selection", SelectionList)
            selected_langs = lang_list.selected
            if "en" not in selected_langs:
                selected_langs.append("en")

            status_label = self.query_one("#config-status", Label)

            # Save
            cfg = config.load_config()
            cfg["server_port"] = int(port_val) if port_val.isdigit() else 5050
            # cfg["threads"] ... (If we saved these, but config.py default dict only has minimal. We can add them.)
            # For now, let's strictly save the languages which was the request.
            cfg["libretranslate_languages"] = selected_langs
            
            config.save_config(cfg)
            
            status_label.update("✓ Configuration Saved! Restart Server to Apply.")
            self.log_widget.write_line(f"Saved Config. Languages: {selected_langs}")
            
        except Exception as e:
            self.log_widget.write_line(f"Save Config Failed: {e}")
            if 'status_label' in locals():
                status_label.update(f"Error: {e}")

    def start_server(self):
        selection_list = self.query_one("#lang-selection", SelectionList)
        selected = selection_list.selected
        port_input = self.query_one("#input-port", Input)
        port_val = port_input.value
        
        threads_val = self.query_one("#input-threads", Input).value
        char_val = self.query_one("#input-char", Input).value
        batch_val = self.query_one("#input-batch", Input).value
        cache_val = self.query_one("#chk-cache", Checkbox).value
        
        # Get translation model from config
        cfg = config.load_config()
        translation_model = cfg.get("translation_model", "libretranslate")
        
        debug_checkbox = self.query_one("#checkbox-debug-log", Checkbox)
        debug_enabled = debug_checkbox.value
        
        if "en" not in selected:
            selected.append("en")
            
        langs_str = ",".join(selected)
        
        self.log_widget.write_line("-" * 30)
        self.log_widget.write_line(f"Starting server with: {langs_str} on Port {port_val}")
        self.log_widget.write_line(f"Translation Model: {translation_model.upper()}")
        self.log_widget.write_line(f"Debug Logging: {'ON' if debug_enabled else 'OFF'}")
        if translation_model == 'libretranslate':
            self.log_widget.write_line("Please wait (~10-30s) for models to load...")
        else:
            self.log_widget.write_line("Using IndicTrans2 - no Argos models needed...")
        
        # Update UI
        self.status_ind.update("STARTING...")
        self.status_ind.styles.background = "#bd93f9" # Purple
        self.status_ind.remove_class("ready")
        
        # Start Thread
        self.thread = ServerThread(
            langs_str, port_val, self.log_to_widget, debug_enabled,
            threads=threads_val, char_limit=char_val, batch_limit=batch_val, 
            translation_cache=cache_val, translation_model=translation_model
        )
        self.thread.start()
        
        # Assume success after a delay or implement check
        self.set_interval(2, self.check_alive)
        self.server_running = True

    def log_to_widget(self, msg):
        # Must be called thread-safely? Textual handles `call_from_thread` usually
        self.call_from_thread(self.log_widget.write_line, str(msg))

    def check_alive(self):
        # We can poll localhost:5050/health here?
        if self.server_running:
            port_input = self.query_one("#input-port", Input) # Might be dangerous to access if removed? No.
            p = port_input.value
            self.status_ind.update(f"ONLINE (Port {p})")
            self.status_ind.add_class("online")

# Helper to redirect streams to Textual Log
class TextualStream:
    def __init__(self, write_func):
        self.write_func = write_func
    def write(self, message):
        if message.strip():
            # Use call_from_thread if this is called from thread
            self.write_func(message.strip())
    def flush(self):
        pass

if __name__ == "__main__":
    app = XglishApp()
    
    # Correct way: Add a logging Handler that pushes to the app
    class WidgetHandler(logging.Handler):
        def __init__(self, app_ref):
            super().__init__()
            self.app_ref = app_ref
            
        def emit(self, record):
            msg = self.format(record)
            try:
                if self.app_ref.log_widget:
                    self.app_ref.call_from_thread(self.app_ref.log_widget.write_line, msg)
            except (RuntimeError, Exception):
                pass

    # We attach this handler in on_mount
    
    # Patch the App class to add the handler on mount
    original_mount = XglishApp.on_mount
    
    def new_on_mount(self):
        original_mount(self)
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        # Create timestamped log files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        access_log = os.path.join(log_dir, f'xglish_{timestamp}_access.log')
        app_log = os.path.join(log_dir, f'xglish_{timestamp}_app.log')
        
        # TUI handler (shows everything)
        tui_handler = WidgetHandler(self)
        tui_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%H:%M:%S')
        tui_handler.setFormatter(tui_formatter)
        
        # Access log handler (HTTP requests only)
        access_handler = logging.FileHandler(access_log, encoding='utf-8')
        access_formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        access_handler.setFormatter(access_formatter)
        access_handler.setLevel(logging.INFO)
        
        # App log handler (errors and debug info only)
        app_handler = logging.FileHandler(app_log, encoding='utf-8')
        app_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        app_handler.setFormatter(app_formatter)
        app_handler.setLevel(logging.INFO)
        
        # Configure Werkzeug logger (HTTP access logs)
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.addHandler(tui_handler)
        werkzeug_logger.addHandler(access_handler)
        werkzeug_logger.setLevel(logging.INFO)
        werkzeug_logger.propagate = False  # STOP propagation to root logger!
        
        # Configure Root logger (application logs)
        root_logger = logging.getLogger()
        root_logger.addHandler(tui_handler)
        root_logger.addHandler(app_handler)
        root_logger.setLevel(logging.INFO)
        
        # Log the file locations
        self.log_widget.write_line(f"Access logs: {access_log}")
        self.log_widget.write_line(f"App logs: {app_log}")
        
    XglishApp.on_mount = new_on_mount

    app.run()
