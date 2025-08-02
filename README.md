# About the app
Aliasify is a Streamlit app that helps you mask named entities in your text before sending it to a large language model (LLM), and restore them afterwards—all locally in your browser session. The app uses spaCy to automatically detect entities, lets you review and tweak replacements, and encode/decode text for privacy. No data leaves your browser.

# Run app
1. Create a virtual environment: `python3 -m venv venv`
2. Activate the virtual environment: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run the app: `python -m streamlit run streamlit_anonymise_app.py`