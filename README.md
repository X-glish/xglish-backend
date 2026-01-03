# Xglish Backend

This directory contains the Python backend service for the Xglish Safari Extension. It acts as a local server that processes text for Hinglish mixing, transliteration, and Romanization.

## Architecture

The system is built on a modular architecture optimized for speed and quality:

*   **`server_extension.py`**: The Flask application entry point. Handles HTTP requests (`POST /transliterate`) and orchestrates the pipeline. **Smartly switches modes**:
    *   **IndicTrans2 Mode**: Lightweight Flask app, skips LibreTranslate loading.
    *   **LibreTranslate Mode**: Full LibreTranslate integration.
*   **`xglish_mixer.py`**: **Core V2 Mixing Logic**. Implements the "Translate-First" algorithm:
    1.  Translates full sentence to Indic (preserving grammar).
    2.  Romanizes the output via Aksharamukha.
    3.  Selectively restores common English words ("Hello", "Thanks", etc.) for natural code-mixing.
*   **`translator_service.py`**: Manages translation models with **True Batch Inference**:
    *   **IndicTrans2**: High-quality English-to-Indic translation. Uses GPU-accelerated batch processing (14x faster than sequential).
    *   **LibreTranslate**: Fallback translation service.
*   **`nlp_engine.py`**: Handles basic NLP tasks (Tokenization, POS Tagging).
*   **`resource_loader.py`**: Loads dictionaries and whitelist data.
*   **`config.py`**: Configuration management.

## Prerequisites

*   **Python 3.12+**
*   **Virtual Environment**: Strongly recommended.

### Dependencies
Install the required packages:
```bash
pip install flask nltk spacy torch transformers setuptools wordfreq aksharamukha
```

### Models
*   **IndicTrans2**: Automatically downloaded (`ai4bharat/indictrans2-en-indic-dist-200M`).
*   **Spacy/NLTK**: Standard English models.

## Running the Server

1.  Activate your environment:
    ```bash
    source /path/to/venv/bin/activate
    ```
2.  Start the service:
    ```bash
    python server_extension.py
    ```
3.  The server checks `config.json` (or UI settings) to decide which model to load.
    *   **IndicTrans2 Mode**: Fast startup (once model weighs are cached), optimized for Indic languages.
    *   **LibreTranslate Mode**: Loads Argos models (slower startup).

## API Endpoints

### `POST /transliterate`
**Payload:**
```json
{
  "q": ["Text to process", "Another string"],
  "target": "Hinglish_Mix", 
  "threshold": 7.0
}
```
*   `q`: List of strings (recommended for speed) or single string.

#### Target Options

| Target | Description | Example Output |
|--------|-------------|----------------|
| **Smart Mix V2 (Grammar Preserved)** |||
| `Hindi_Mix` / `Hinglish_Mix` | English→Hinglish | `"Hello, aap kaise hain?"` |
| `Tamil_Mix` | English→Tanglish | `"Hello, eppadi irukkeenga?"` |
| `Bengali_Mix` | English→Benglish | `"Hello, apni kemon achhen?"` |
| `Telugu_Mix` | English→Tenglish | `"Hello, meeru ela unnaru?"` |
| `Marathi_Mix` | English→Marathlish | `"Hello, tumhi kase aahat?"` |
| `Gujarati_Mix` | English→Gujlish | `"Hello, tame kem chho?"` |
| `Malayalam_Mix` | English→Manglish | `"Hello, ningal engane und?"` |
| `Kannada_Mix` | English→Kanglish | `"Hello, neevu hegiddira?"` |
| `Punjabi_Mix` | English→Punglish | `"Hello, tusi kive ho?"` |
| `Urdu_Mix` | English→Urdish | `"Hello, aap kaise hain?"` |
| **Full Romanization** |||
| `Roman_hi` | English→Hindi→Roman | `"namaste, aap kaise hain?"` |
| `Roman_ta` | English→Tamil→Roman | `"vanakkam, eppadi irukkeenga?"` |
| `Roman_bn` | English→Bengali→Roman | `"namaskaar, aapni kemon aachhen?"` |
| `Roman_te` | English→Telugu→Roman | `"namaskaram, meeru ela unnaru?"` |
| `Roman_mr` | English→Marathi→Roman | `"namaskaar, tumhi kase aahat?"` |
| `Roman_ml` | English→Malayalam→Roman | `"namaskaram, ningal engane und?"` |
| `RomanColloquial` | Alias for `Roman_hi` | `"namaste, aap kaise hain?"` |
| **Script Conversion** |||
| `Devanagari` | Roman→Devanagari | `"नमस्ते"` |
| `Bengali` | Roman→Bengali | `"নমস্কার"` |
| `Tamil` | Roman→Tamil | `"வணக்கம்"` |
| `Telugu` | Roman→Telugu | `"నమస్కారం"` |

> **Key Difference:** `*_Mix` keeps common English words (based on threshold), `Roman_*` translates everything.

**Response:**
```json
{
  "success": true,
  "results": ["Processed text", "Another processed string"]
}
```

### `GET /health`
Returns `{"status": "online", "success": true}`.

## Performance Highlights

*   **Batch Inference**: Processing 5 texts now takes **~1s** (vs ~15s previously), a **14x speedup**.
*   **V2 Mixing**: Uses full-sentence translation to ensure correct SOV (Subject-Object-Verb) grammar for Indic languages, unlike the old word-replacement method.

## Known Issues

*   **First Run**: The first translation request might take 10-20s while the model loads into memory. Subsequent batch requests are sub-second.

## Acknowledgments & Status

**Status**: 🚧👷‍♂️ Under Development! Needs Contributions & Feedbacks!

This project relies on and builds upon the excellent work of several open-source projects:

*   **[IndicTrans2](https://github.com/AI4Bharat/IndicTrans2)**: For state-of-the-art English-Indic translation models.
*   **[Aksharamukha](https://github.com/virtualvinodh/aksharamukha)**: For script conversion and Romanization logic.
*   **[LibreTranslate](https://github.com/LibreTranslate/LibreTranslate)**: For offline translation support.
*   **[IndicEn](https://github.com/subins2000/indicen)**: foundational work on Indic-English transliteration that inspired parts of this project.

We are grateful to the maintainers of these projects for their contributions to the NLP ecosystem.


## API Usage (cURL Examples)

### 1. Smart Mix (English -> Hinglish)
```bash
curl -X POST http://localhost:5050/transliterate \
  -H "Content-Type: application/json" \
  -d '{
    "q": ["Hello world", "How are you?"],
    "target": "Hinglish_Mix",
    "threshold": 7
  }'
```

### 2. Multilingual Mix (English -> Tamil Mix)
```bash
curl -X POST http://localhost:5050/transliterate \
  -H "Content-Type: application/json" \
  -d '{
    "q": "This is a test message.",
    "source": "en",
    "target": "Tamil_Mix",
    "threshold": 7
  }'
```

### 3. Roman Colloquial (English -> Romanized Hindi)
Translates English to Hindi, then converts the script to readable Roman text.
```bash
curl -X POST http://localhost:5050/transliterate \
  -H "Content-Type: application/json" \
  -d '{
    "q": "How are you?",
    "source": "en",
    "target": "RomanColloquial"
  }'
```
