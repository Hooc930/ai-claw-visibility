# AI Claw Visibility Analyzer ⚡

**See exactly how visible your brand is inside ChatGPT, Gemini, and Claude — using real browser automation, zero API keys.**

## 🚀 Live Demo
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ai-claw-visibility.streamlit.app)

## What it does
- Crawls your website to understand your brand
- Generates 12 high-intent buyer prompts
- Visits ChatGPT, Gemini, and Claude **as a real user** (Playwright browser automation)
- Measures your brand visibility, sentiment, and citation sources
- Scores you 0–100 with actionable recommendations

## Run locally
```bash
git clone https://github.com/Hooc930/ai-claw-visibility
cd ai-claw-visibility
pip install -r requirements.txt
playwright install chromium
streamlit run app.py
```

## Tech
- Streamlit · Playwright · Trafilatura · TextBlob · Pandas · Plotly · SQLite
