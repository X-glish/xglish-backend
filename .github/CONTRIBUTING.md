# Contributing to Xglish Backend

First off, thank you for considering contributing to Xglish! We are building the best engine for Hinglish, Tanglish, and Indic-Mix generation.

We welcome valuable contributions. By participating in this project, you agree to abide by our Code of Conduct.

## How Can I Contribute?

### 💡 Ideas & Architecture Overhauls
We are **Open to Innovation**! 
*   Have a crazy idea to rewrite the Mixer logic?
*   Think a different model architecture would work better?
*   Want to restructure the entire pipeline?

**We accept major architectural changes** if you can prove they are better (faster, higher quality, or easier to maintain). Don't be afraid to propose big changes!

### Key Areas for Contribution
We are specifically looking for help with:
*   **Mixing Rules**: Improving the `xglish_mixer.py` logic to make the "English-Indic" mix feel more natural (e.g., better word choice).
*   **Language Support**: Adding support for more Indic languages in `language_rules.py`.
*   **Performance**: Optimizing the Inference pipeline for low-resource devices.
*   **Tests**: Creating automated test cases for different languages.

### Reporting Bugs
*   **Context Matters**: Since we use AI models (IndicTrans2), please specify if the issue is a Translation Error (model output) or a System Error (crash).
*   **Include Config**: Mention which model you are running (`libretranslate` or `indictrans2`) in your report.

### Pull Requests
1.  **Fork & Clone**: Standard GitHub flow.
2.  **Branch Name**: `feat/better-tamil-mixing` or `fix/crash-on-startup`.
3.  **Test Your Changes**:
    *   If changing `xglish_mixer.py`, run a few manual `curl` tests to verify the output quality.
    *   Ensure strict JSON output from API endpoints.
4.  **Submit PR**: detailed description of why this mix/fix is better.

## Development Guidelines

### Architecture Overview
*   **`xglish_mixer.py`**: The heart of the logic. `process_mixed_english_v2` controls the "Translate -> Romanize -> Restore English" pipeline.
*   **`translator_service.py`**: Wraps the ML models. Ensure any changes here support Batching (LIST input) to keep performance high.
*   **`server_extension.py`**: The API layer. Keep it lightweight.

### Models Warning
If you are working on `IndicTrans2` features, be aware:
*   We use the **200M Distilled Model** by default.
*   It requires **~1GB RAM** (CPU) to run smoothly.
*   First run will download model weights (~1GB).

### Adding a New Language
1.  Add the language code to `ISO_TO_INDICTRANS2` in `config.py` (or `translator_service.py`).
2.  Update `language_rules.py` with the script name for Aksharamukha (e.g., `'Gujarati': 'Gujarati'`).
3.  Test the `*_Mix` target (e.g., `Gujarati_Mix`).

## Stylechecks
*   We follow PEP 8.
*   **Type Hinting**: Encouraged for new function signatures.
*   **Comments**: Explain complex mixing logic, not obvious code.

## Questions?
Open an issue with the label `question`. We are happy to help you get started!

---
Thanks!

The ❤️Xglish Team
