# ╔══════════════════════════════════════════════════════════════════════════╗
# ║           AI CLAW VISIBILITY ANALYZER — v2 (Browser-Only)              ║
# ║  Architecture: Pure Playwright browser automation, zero API keys        ║
# ║  Querying: chatgpt.com · gemini.google.com · claude.ai                 ║
# ╚══════════════════════════════════════════════════════════════════════════╝
import streamlit as st

st.set_page_config(
    page_title="AI Claw Visibility Analyzer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

import asyncio, json, sqlite3, os, re, time, random, traceback
from datetime import datetime
from urllib.parse import urlparse, urljoin
from collections import Counter

import pandas as pd
import plotly.graph_objects as go

# ── Optional imports (graceful degradation) ───────────────────────────────────
try:
    import trafilatura
    from bs4 import BeautifulSoup
    HAS_CRAWL = True
except ImportError:
    HAS_CRAWL = False

try:
    from textblob import TextBlob
    HAS_TEXTBLOB = True
except ImportError:
    HAS_TEXTBLOB = False

try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

try:
    import boto3
    HAS_BEDROCK = True
except ImportError:
    HAS_BEDROCK = False


# ── Constants ─────────────────────────────────────────────────────────────────
DB_PATH   = "/home/ubuntu/clawd/ai-claw-visibility/analyses.db"
MODELS    = ["ChatGPT", "Gemini", "Claude"]
COUNTRIES = {"US": "United States", "UK": "United Kingdom", "DE": "Germany",
             "FR": "France", "IL": "Israel"}

MODEL_URLS = {
    "ChatGPT": "https://chatgpt.com/",
    "Gemini":  "https://gemini.google.com/app",
    "Claude":  "https://claude.ai/new",
}

MODEL_COLORS = {"ChatGPT": "#10a37f", "Gemini": "#8b5cf6", "Claude": "#f59e0b"}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]

SOURCE_CATEGORIES = {
    "wikipedia.org": "Wikipedia",    "reddit.com": "Review/UGC",
    "g2.com": "Review/UGC",          "trustpilot.com": "Review/UGC",
    "capterra.com": "Review/UGC",    "producthunt.com": "Review/UGC",
    "getapp.com": "Review/UGC",      "techcrunch.com": "Editorial",
    "wired.com": "Editorial",        "forbes.com": "Editorial",
    "cnet.com": "Editorial",         "theverge.com": "Editorial",
    "medium.com": "Editorial",       "venturebeat.com": "Editorial",
    "zdnet.com": "Editorial",        "twitter.com": "Social",
    "x.com": "Social",               "linkedin.com": "Social",
    "youtube.com": "Social",         "github.com": "Corporate",
    "stackoverflow.com": "Editorial","quora.com": "Review/UGC",
}


# ── Premium CSS ───────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; }

/* ── Hero ── */
.hero {
    background: linear-gradient(135deg,#0a0a0f 0%,#0d1829 45%,#091520 75%,#0a0a0f 100%);
    background-size: 400% 400%;
    animation: bg-shift 12s ease infinite;
    border-bottom: 1px solid #1e3a5f;
    padding: 1.6rem 2.2rem 1.4rem;
    margin: -1rem -1rem 1.8rem -1rem;
    border-radius: 0 0 16px 16px;
    display: flex; align-items: center; gap: 1rem;
}
@keyframes bg-shift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.hero-logo {
    font-family: 'Space Mono', monospace !important;
    font-size: 2rem; font-weight: 700; line-height: 1;
    background: linear-gradient(90deg,#3b82f6,#06b6d4);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; letter-spacing: 0.04em;
}
.hero-claw { font-size: 2.4rem; line-height: 1; }
.hero-sub {
    color: #475569; font-size: 0.78rem; letter-spacing: 0.18em;
    text-transform: uppercase; margin-top: 3px;
}
.hero-badge {
    margin-left: auto; background: #0f2744; border: 1px solid #1e3a5f;
    border-radius: 20px; padding: 4px 12px; font-size: 0.72rem;
    color: #06b6d4; letter-spacing: 0.05em;
}

/* ── Cards ── */
.card {
    background: linear-gradient(135deg,#111118,#0f1729);
    border: 1px solid #1e3a5f; border-radius: 12px;
    padding: 1.4rem; margin: 0.4rem 0;
    box-shadow: 0 4px 20px rgba(59,130,246,.07);
    transition: border-color .3s, box-shadow .3s;
}
.card:hover { border-color: #3b82f6; box-shadow: 0 4px 28px rgba(59,130,246,.15); }
.card-title { color: #94a3b8; font-size: 0.78rem; letter-spacing: 0.1em;
              text-transform: uppercase; margin-bottom: 0.4rem; }
.card-value { font-family: 'Space Mono', monospace; font-size: 1.8rem;
              font-weight: 700; color: #e2e8f0; }
.card-value-sm { font-size: 1.2rem; }

/* ── Gradient-border metric ── */
.gm {
    background: #111118; border-radius: 12px; padding: 1.1rem 1.3rem;
    position: relative; overflow: hidden;
}
.gm::before {
    content:''; position:absolute; inset:0; border-radius:12px; padding:1px;
    background: linear-gradient(135deg,#3b82f6,#06b6d4);
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
}

/* ── Status log ── */
.log-box {
    background: #07090e; border: 1px solid #1a2f4a; border-radius: 8px;
    padding: 0.9rem 1rem; font-family: 'Space Mono', monospace;
    font-size: 0.75rem; color: #38bdf8; max-height: 240px;
    overflow-y: auto; line-height: 1.9;
}

/* ── Insight ── */
.insight {
    background: linear-gradient(135deg,#0f1729,#111827);
    border-left: 3px solid #3b82f6; border-radius: 0 8px 8px 0;
    padding: 0.9rem 1.2rem; margin: 0.45rem 0;
    font-size: 0.9rem; color: #e2e8f0; line-height: 1.6;
}

/* ── Rec boxes ── */
.rec-high   { border-left: 3px solid #ef4444 !important; }
.rec-medium { border-left: 3px solid #f59e0b !important; }
.rec-low    { border-left: 3px solid #22c55e !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #111118; border-radius: 10px; padding: 4px; gap: 3px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 7px; padding: 7px 16px;
    font-size: 0.83rem; font-weight: 500;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0a0a0f; border-right: 1px solid #1e3a5f;
}
.sb-note {
    background: #0d1729; border: 1px solid #1e3a5f; border-radius: 8px;
    padding: 0.7rem 0.9rem; font-size: 0.8rem; color: #06b6d4;
    line-height: 1.5; margin: 0.5rem 0;
}

/* ── Big run button ── */
.stButton > button {
    background: linear-gradient(135deg,#2563eb,#3b82f6) !important;
    color: #fff !important; border: none !important;
    border-radius: 9px !important; padding: 0.65rem 1.5rem !important;
    font-weight: 600 !important; font-size: 0.95rem !important;
    letter-spacing: 0.025em !important;
    box-shadow: 0 4px 18px rgba(59,130,246,.3) !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 24px rgba(59,130,246,.4) !important;
}

/* ── Progress ── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg,#3b82f6,#06b6d4) !important;
    border-radius: 4px !important;
}

/* ── Score colors ── */
.score-green  { color: #22c55e !important; }
.score-yellow { color: #f59e0b !important; }
.score-red    { color: #ef4444 !important; }

/* ── Model badges ── */
.badge { border-radius:20px; padding:2px 10px; font-size:0.74rem; font-weight:600; }
.badge-ChatGPT { background:#10a37f22; border:1px solid #10a37f; color:#10a37f; }
.badge-Gemini  { background:#8b5cf622; border:1px solid #8b5cf6; color:#8b5cf6; }
.badge-Claude  { background:#f59e0b22; border:1px solid #f59e0b; color:#f59e0b; }

/* ── Empty state ── */
.empty-state {
    text-align:center; padding:3.5rem 2rem;
}
.empty-icon { font-size:4rem; margin-bottom:1rem; }
.empty-title { color:#e2e8f0; font-size:1.55rem; font-weight:600;
               font-family:'DM Sans',sans-serif; margin-bottom:.8rem; }
.empty-sub { color:#475569; max-width:580px; margin:0 auto;
             font-size:1rem; line-height:1.75; }
.empty-hint {
    text-align:center; margin-top:2rem; padding:1rem;
    background:#111118; border:1px dashed #1e3a5f;
    border-radius:12px; color:#475569; font-size:.9rem;
}
.feature-card {
    background: linear-gradient(135deg,#111118,#0f1729);
    border:1px solid #1e3a5f; border-radius:12px; padding:1.4rem;
    text-align:center; height:100%;
}
.feature-icon { font-size:1.8rem; margin-bottom:.5rem; }
.feature-title { color:#3b82f6; font-weight:600; margin-bottom:.4rem; }
.feature-desc { color:#64748b; font-size:.85rem; line-height:1.6; }

/* ── DataFrames ── */
.stDataFrame { border:1px solid #1e3a5f !important; border-radius:8px !important; }
div[data-testid="stDataFrameResizable"] { border-radius:8px; overflow:hidden; }

/* ── Expanders ── */
details summary { font-weight:500; }
</style>
"""


# ╔══════════════════════════════════════════════════════════════╗
# ║  DATABASE                                                    ║
# ╚══════════════════════════════════════════════════════════════╝
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS analyses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        url TEXT NOT NULL,
        brand TEXT NOT NULL,
        score REAL NOT NULL,
        json_data TEXT NOT NULL
    )""")
    conn.commit(); conn.close()

def save_analysis(url, brand, score, data):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT INTO analyses(timestamp,url,brand,score,json_data) VALUES(?,?,?,?,?)",
        (datetime.now().isoformat(), url, brand, score, json.dumps(data, default=str))
    )
    conn.commit(); conn.close()

def load_recent(n=5):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id,timestamp,url,brand,score FROM analyses ORDER BY timestamp DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close(); return rows

def load_by_id(aid):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT json_data FROM analyses WHERE id=?", (aid,)).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


# ╔══════════════════════════════════════════════════════════════╗
# ║  STEP A — SITE INTELLIGENCE & PROMPT GENERATION             ║
# ╚══════════════════════════════════════════════════════════════╝
def extract_domain(url: str) -> str:
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d

def brand_from_domain(domain: str) -> str:
    return domain.split(".")[0].replace("-"," ").replace("_"," ").title()

def crawl_site(url: str, log) -> str:
    """Fetch homepage + up to 3 internal links via trafilatura."""
    if not HAS_CRAWL:
        log("⚠️  trafilatura not available — skipping crawl")
        return ""
    texts, seen_links = [], set()
    log(f"🌐 Crawling {url} …")
    try:
        raw = trafilatura.fetch_url(url)
        if raw:
            t = trafilatura.extract(raw, include_links=False, include_comments=False,
                                    favor_recall=True)
            if t: texts.append(t)
            # Collect internal links
            soup = BeautifulSoup(raw, "html.parser")
            base = extract_domain(url)
            for a in soup.find_all("a", href=True):
                full = urljoin(url, a["href"])
                fd = extract_domain(full)
                if fd == base and full not in seen_links and full != url and "?" not in full:
                    seen_links.add(full)
                if len(seen_links) >= 6:
                    break
    except Exception as e:
        log(f"⚠️  Homepage crawl error: {e}")

    for link in list(seen_links)[:3]:
        try:
            log(f"  ↳ {link}")
            raw2 = trafilatura.fetch_url(link)
            if raw2:
                t2 = trafilatura.extract(raw2, favor_recall=True)
                if t2: texts.append(t2)
        except Exception:
            pass

    return "\n\n".join(texts)


def bedrock_generate_prompts(brand, domain, tagline, products, topics, competitors, n) -> list[str] | None:
    """Call Bedrock Claude Haiku to generate smarter prompts (optional)."""
    if not HAS_BEDROCK:
        return None
    try:
        client = boto3.client("bedrock-runtime", region_name="us-east-1")
        comp_str = ", ".join(competitors[:4]) if competitors else "industry alternatives"
        prod_str = ", ".join(products[:3]) if products else "software"
        topic_str = ", ".join(topics[:3]) if topics else "technology"
        sys_msg = "You are an SEO and AI-visibility expert."
        user_msg = (
            f"Generate exactly {n} high-intent conversational search prompts that real users "
            f"would type into ChatGPT, Gemini, or Claude when researching tools like '{brand}'.\n\n"
            f"Context:\n"
            f"- Brand: {brand} ({domain})\n"
            f"- Description: {tagline[:200] if tagline else 'N/A'}\n"
            f"- Products/services: {prod_str}\n"
            f"- Topics: {topic_str}\n"
            f"- Main competitors: {comp_str}\n\n"
            f"Rules:\n"
            f"- Mix brand-specific (40%) and category-level (60%) queries\n"
            f"- Include: review queries, comparison queries, 'best X for Y' queries, "
            f"'should I use' queries, alternative queries\n"
            f"- Year: 2025 or 2026\n"
            f"- Return ONLY a JSON array of {n} strings, no explanation.\n"
            f'Example: ["best CRM for startups 2025", "is HubSpot worth it for small teams", ...]'
        )
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 600,
            "system": sys_msg,
            "messages": [{"role": "user", "content": user_msg}]
        })
        resp = client.invoke_model(
            modelId="us.anthropic.claude-3-5-haiku-20241022-v1:0",
            body=body, contentType="application/json", accept="application/json"
        )
        result = json.loads(resp["body"].read())
        text = result["content"][0]["text"].strip()
        # Extract JSON array
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            prompts = json.loads(m.group())
            if isinstance(prompts, list) and len(prompts) >= n:
                return [str(p) for p in prompts[:n]]
    except Exception as e:
        pass  # Fall through to template prompts
    return None


def generate_prompts_template(brand, domain, topics, competitors, n) -> list[str]:
    """Template-based prompt generation (always works, no API needed)."""
    c = competitors[0] if competitors else "alternatives"
    cat = topics[0].lower() if topics else "software"
    uc  = topics[1].lower() if len(topics) > 1 else "businesses"

    templates = [
        f"best {cat} tools for {uc} in 2025",
        f"is {brand} worth it for {uc}",
        f"{brand} review 2025",
        f"alternatives to {brand}",
        f"should I use {brand} for {uc}",
        f"{brand} vs {c}",
        f"top {cat} platforms for small businesses 2025",
        f"how does {brand} compare to competitors",
        f"best {cat} software recommendations 2025",
        f"{brand} pricing and features breakdown",
        f"what companies use {brand}",
        f"is {brand} the best {cat} solution",
        f"{brand} pros and cons",
        f"which is better {brand} or {c}",
        f"best {cat} for startups 2025",
        f"{brand} integrations and use cases",
        f"how to choose between {brand} and {c}",
        f"top rated {cat} tools experts recommend 2025",
        f"{brand} customer reviews and ratings",
        f"enterprise {cat} solutions compared 2025",
    ]
    return templates[:n]


def analyze_site(url: str, brand_override: str, num_prompts: int, log) -> dict:
    """Full Step A pipeline: crawl → extract intel → generate prompts."""
    domain     = extract_domain(url)
    brand      = brand_override.strip() or brand_from_domain(domain)
    site_text  = crawl_site(url, log)

    tagline, products, topics, competitors = "", [], [], []

    if site_text:
        lines = [l.strip() for l in site_text.split("\n") if l.strip()]
        # Tagline = first line mentioning brand or first shortish line
        for line in lines[:15]:
            if 20 < len(line) < 180:
                tagline = line; break

        # Products — match "our X platform/tool/service" patterns
        prod_re = re.compile(
            r'(?:our|the)\s+([A-Z][a-zA-Z\s]{2,25}?)\s+'
            r'(?:platform|software|tool|service|product|solution|app|suite)',
            re.IGNORECASE
        )
        for m in prod_re.finditer(site_text[:5000]):
            p = m.group(1).strip().title()
            if p.lower() not in brand.lower() and p not in products:
                products.append(p)
            if len(products) >= 5: break

        # Topics — keyword scan
        TOPIC_KW = [
            "analytics","marketing","AI","automation","data","cloud","security",
            "e-commerce","CRM","SEO","content","social media","email","payments",
            "HR","ERP","productivity","collaboration","DevOps","cybersecurity",
            "customer support","sales","finance","recruitment","legal","healthcare",
        ]
        topics = [kw for kw in TOPIC_KW if kw.lower() in site_text.lower()][:6]

        # Competitors — scan for known brand names
        COMP_POOL = [
            "HubSpot","Salesforce","Mailchimp","Shopify","WordPress","Notion",
            "Monday","Asana","Slack","Zoom","Figma","Canva","Semrush","Ahrefs",
            "Moz","Hotjar","Mixpanel","Amplitude","Intercom","Zendesk","Freshdesk",
            "Jira","Confluence","Trello","ClickUp","Linear","Webflow","Squarespace",
            "Wix","BigCommerce","Magento","Stripe","PayPal","Braintree","Twilio",
            "SendGrid","Klaviyo","ActiveCampaign","Marketo","Pardot","Eloqua",
        ]
        competitors = [
            c for c in COMP_POOL
            if c.lower() != brand.lower() and c.lower() in site_text.lower()
        ][:6]

    log(f"✅ Brand: {brand}  |  Domain: {domain}")
    log(f"   Topics: {', '.join(topics[:4]) or 'general'}")
    log(f"   Competitors detected: {', '.join(competitors[:3]) or 'none'}")

    # Try Bedrock for smarter prompts; fall back to templates
    prompts = None
    if HAS_BEDROCK and site_text:
        log("🤖 Using Bedrock Claude Haiku for prompt generation …")
        prompts = bedrock_generate_prompts(
            brand, domain, tagline, products, topics, competitors, num_prompts
        )
        if prompts:
            log(f"✅ Bedrock generated {len(prompts)} prompts")
        else:
            log("⚠️  Bedrock prompt generation failed — using template prompts")

    if not prompts:
        prompts = generate_prompts_template(brand, domain, topics, competitors, num_prompts)
        log(f"✅ Generated {len(prompts)} template prompts")

    return {
        "brand": brand, "domain": domain, "tagline": tagline,
        "products": products, "topics": topics, "competitors": competitors,
        "prompts": prompts,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║  STEP B — PLAYWRIGHT BROWSER AUTOMATION                     ║
# ║  Pure real-user simulation. Zero API keys.                   ║
# ╚══════════════════════════════════════════════════════════════╝

# ── helpers ──────────────────────────────────────────────────────────────────
async def _safe_fill(page, selectors: list, text: str, timeout=8000) -> bool:
    """Try a list of CSS/xpath selectors; fill the first one that exists."""
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=timeout, state="visible")
            if el:
                await el.click()
                await el.fill(text)
                return True
        except Exception:
            continue
    return False

async def _safe_text(page, selectors: list, timeout=10000) -> str:
    """Return inner_text of the first matching selector."""
    for sel in selectors:
        try:
            el = await page.wait_for_selector(sel, timeout=timeout)
            if el:
                return (await el.inner_text()).strip()
        except Exception:
            continue
    return ""

async def _wait_stream_stop(page, sel: str, stable_ms=3000, timeout_s=55):
    """
    Poll a selector until its text stops growing for `stable_ms` ms,
    or until `timeout_s` seconds have passed.
    """
    deadline = time.time() + timeout_s
    last_len  = -1
    stable_since = None
    while time.time() < deadline:
        try:
            txt = await page.inner_text(sel)
            cur_len = len(txt)
            if cur_len == last_len:
                if stable_since is None:
                    stable_since = time.time()
                elif time.time() - stable_since >= stable_ms / 1000:
                    return txt
            else:
                last_len     = cur_len
                stable_since = None
        except Exception:
            pass
        await asyncio.sleep(0.7)
    # Return whatever we have
    try:
        return await page.inner_text(sel)
    except Exception:
        return ""

def _is_login_wall(url: str) -> bool:
    lowers = url.lower()
    return any(k in lowers for k in ("login", "signin", "sign-in", "auth", "accounts.google"))


# ── ChatGPT ──────────────────────────────────────────────────────────────────
async def query_chatgpt(context, prompt: str) -> dict:
    page = await context.new_page()
    r = {"model":"ChatGPT","prompt":prompt,"response":"","sources":[],"mock":False,"error":None}
    try:
        await page.goto("https://chatgpt.com/", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2500)

        if _is_login_wall(page.url):
            r["error"] = "login_required"
            r["response"] = "[Login required — ChatGPT redirected to login page]"
            return r

        # --- input ---
        INPUT_SELS = [
            '#prompt-textarea',
            'textarea[data-id="root"]',
            'textarea[placeholder]',
            'div[contenteditable="true"]',
            'textarea',
        ]
        filled = await _safe_fill(page, INPUT_SELS, prompt, timeout=10000)
        if not filled:
            r["error"] = "input_not_found"
            r["response"] = "[Could not find ChatGPT input field]"
            return r

        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

        # --- wait for response to stop streaming ---
        RESP_SELS = [
            '[data-message-author-role="assistant"]',
            '.agent-turn',
            '.markdown.prose',
            '[class*="prose"]',
        ]
        resp_sel = None
        for sel in RESP_SELS:
            try:
                await page.wait_for_selector(sel, timeout=20000, state="visible")
                resp_sel = sel
                break
            except Exception:
                continue

        if resp_sel:
            r["response"] = await _wait_stream_stop(page, resp_sel, stable_ms=3000, timeout_s=50)
        else:
            await page.wait_for_timeout(18000)
            r["response"] = await page.inner_text("main") or await page.inner_text("body")

        # --- sources: look for citation links in the response turn ---
        try:
            links = await page.eval_on_selector_all(
                'a[href^="http"]',
                "els => els.map(e => e.href)"
            )
            r["sources"] = [l for l in links if "chatgpt.com" not in l][:15]
        except Exception:
            pass

    except Exception as e:
        r["error"] = str(e)
        r["response"] = f"[Browser error: {e}]"
    finally:
        await page.close()
    return r


# ── Gemini ────────────────────────────────────────────────────────────────────
async def query_gemini(context, prompt: str) -> dict:
    page = await context.new_page()
    r = {"model":"Gemini","prompt":prompt,"response":"","sources":[],"mock":False,"error":None}
    try:
        await page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        if _is_login_wall(page.url):
            r["error"] = "login_required"
            r["response"] = "[Login required — Gemini redirected to Google login]"
            return r

        INPUT_SELS = [
            'rich-textarea .ql-editor',
            'rich-textarea div[contenteditable="true"]',
            'textarea[aria-label]',
            'div[contenteditable="true"]',
            '.textarea-container textarea',
            'textarea',
        ]
        filled = await _safe_fill(page, INPUT_SELS, prompt, timeout=12000)
        if not filled:
            # Some Gemini versions use type instead of fill
            for sel in INPUT_SELS:
                try:
                    el = await page.wait_for_selector(sel, timeout=4000)
                    await el.click()
                    await page.keyboard.type(prompt, delay=40)
                    filled = True
                    break
                except Exception:
                    continue

        if not filled:
            r["error"] = "input_not_found"
            r["response"] = "[Could not find Gemini input field]"
            return r

        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2500)

        RESP_SELS = [
            'model-response .response-content',
            'message-content .markdown',
            '[class*="model-response"]',
            'response-container',
            '.conversation-container .response',
            'div[data-response-id]',
        ]
        resp_sel = None
        for sel in RESP_SELS:
            try:
                await page.wait_for_selector(sel, timeout=20000)
                resp_sel = sel
                break
            except Exception:
                continue

        if resp_sel:
            r["response"] = await _wait_stream_stop(page, resp_sel, stable_ms=3000, timeout_s=50)
        else:
            await page.wait_for_timeout(20000)
            try:
                r["response"] = await page.inner_text("main")
            except Exception:
                r["response"] = await page.inner_text("body")

        # sources
        try:
            links = await page.eval_on_selector_all(
                'a[href^="http"]',
                "els => els.map(e => e.href)"
            )
            r["sources"] = [l for l in links if "google.com" not in l][:15]
        except Exception:
            pass

    except Exception as e:
        r["error"] = str(e)
        r["response"] = f"[Browser error: {e}]"
    finally:
        await page.close()
    return r


# ── Claude ────────────────────────────────────────────────────────────────────
async def query_claude(context, prompt: str) -> dict:
    page = await context.new_page()
    r = {"model":"Claude","prompt":prompt,"response":"","sources":[],"mock":False,"error":None}
    try:
        await page.goto("https://claude.ai/new", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(3000)

        if _is_login_wall(page.url):
            r["error"] = "login_required"
            r["response"] = "[Login required — Claude redirected to login page]"
            return r

        INPUT_SELS = [
            'div[contenteditable="true"].ProseMirror',
            '.ProseMirror',
            'div[contenteditable="true"][data-placeholder]',
            'div[contenteditable="true"]',
            'textarea[placeholder]',
            'textarea',
        ]
        filled = await _safe_fill(page, INPUT_SELS, prompt, timeout=12000)
        if not filled:
            for sel in INPUT_SELS:
                try:
                    el = await page.wait_for_selector(sel, timeout=4000)
                    await el.click()
                    await page.keyboard.type(prompt, delay=35)
                    filled = True
                    break
                except Exception:
                    continue

        if not filled:
            r["error"] = "input_not_found"
            r["response"] = "[Could not find Claude input field]"
            return r

        # Claude: press Enter or click send button
        sent = False
        for btn_sel in ['button[aria-label="Send message"]', 'button[type="submit"]',
                        '[data-testid="send-button"]']:
            try:
                btn = await page.wait_for_selector(btn_sel, timeout=3000)
                await btn.click()
                sent = True
                break
            except Exception:
                continue
        if not sent:
            await page.keyboard.press("Enter")

        await page.wait_for_timeout(2500)

        RESP_SELS = [
            '[data-testid="bot-message"]',
            '.font-claude-message',
            '[class*="assistant"]',
            '.prose',
        ]
        resp_sel = None
        for sel in RESP_SELS:
            try:
                await page.wait_for_selector(sel, timeout=20000)
                resp_sel = sel
                break
            except Exception:
                continue

        if resp_sel:
            r["response"] = await _wait_stream_stop(page, resp_sel, stable_ms=3000, timeout_s=50)
        else:
            await page.wait_for_timeout(20000)
            try:
                r["response"] = await page.inner_text("main")
            except Exception:
                r["response"] = await page.inner_text("body")

        try:
            links = await page.eval_on_selector_all(
                'a[href^="http"]', "els => els.map(e => e.href)"
            )
            r["sources"] = [l for l in links if "claude.ai" not in l][:15]
        except Exception:
            pass

    except Exception as e:
        r["error"] = str(e)
        r["response"] = f"[Browser error: {e}]"
    finally:
        await page.close()
    return r


# ── Mock responses ────────────────────────────────────────────────────────────
def mock_response(model: str, prompt: str, brand: str, domain: str, competitors: list) -> dict:
    """Realistic mock responses for demo / testing mode."""
    comp   = competitors[0] if competitors else "CompetitorX"
    comp2  = competitors[1] if len(competitors) > 1 else "AnotherTool"
    mentioned = random.random() < 0.62      # ~62 % mention rate

    src_pool = [
        f"https://g2.com/products/{brand.lower().replace(' ','-')}",
        f"https://trustpilot.com/review/{domain}",
        f"https://capterra.com/software/{brand.lower().replace(' ','-')}",
        "https://techcrunch.com/2025/01/best-tools/",
        "https://forbes.com/advisor/business/",
        "https://reddit.com/r/entrepreneur/comments/tools_2025",
        f"https://wikipedia.org/wiki/{brand.replace(' ','_')}",
        "https://wired.com/story/best-ai-tools-2025/",
        f"https://{domain}",
        f"https://www.{domain}/blog/features",
        "https://producthunt.com/products/",
        "https://venturebeat.com/category/ai/",
    ]
    sources = random.sample(src_pool, random.randint(2, 5))
    src_block = "\n\nSources:\n" + "\n".join(sources)

    if mentioned:
        pos = random.randint(1, 3)
        sent = random.choices(["positive","neutral","negative"], weights=[.55,.35,.10])[0]
        tone = {
            "positive": "is widely praised for its intuitive design and powerful features",
            "neutral":  "is a solid option that suits many use cases depending on your needs",
            "negative": "has received mixed feedback, with some users citing limitations",
        }[sent]
        pre_brands = ", ".join([comp, comp2][:pos-1])
        pre = f"{pre_brands}. " if pre_brands else ""
        body = (
            f"When evaluating tools for this use case in 2025, several platforms stand out.\n\n"
            f"{pre}**{brand}** {tone}. Many teams appreciate its robust integrations and "
            f"competitive pricing. According to reviews on G2 and Trustpilot, users highlight "
            f"the ease of onboarding and responsive support.\n\n"
            f"Key strengths of {brand}:\n"
            f"- Comprehensive feature set for growing teams\n"
            f"- Deep integration ecosystem\n"
            f"- Strong documentation and community\n"
            f"- Transparent pricing tiers\n\n"
            f"{comp} is another popular choice, though {brand} tends to score higher on "
            f"ease-of-use in independent benchmarks."
        )
    else:
        others = [comp, comp2, "HubSpot", "Notion", "Monday.com"]
        body = (
            f"For this use case in 2025, here are the top-rated options:\n\n"
            f"1. **{others[0]}** — Industry leader with enterprise-grade features\n"
            f"2. **{others[1]}** — Best for teams that prioritize flexibility\n"
            f"3. **{others[2]}** — Excellent for smaller teams and solo operators\n"
            f"4. **{others[3]}** — Great all-in-one workspace\n\n"
            f"When deciding, weigh your team size, integration needs, and budget. "
            f"Most platforms offer free trials — test before committing."
        )

    return {
        "model": model, "prompt": prompt,
        "response": body + src_block,
        "sources": sources, "mock": True, "error": None,
    }


# ── Orchestrator ──────────────────────────────────────────────────────────────
async def run_live_queries(
    prompts: list, brand: str, domain: str, competitors: list,
    progress_cb, log
) -> list:
    """
    Launch ONE browser per model; reuse the same page across prompts (faster,
    less fingerprinting noise).  Falls back to mock on any unrecoverable error.
    """
    if not HAS_PLAYWRIGHT:
        log("❌ Playwright not installed — using mock mode")
        return []

    results = []
    total   = len(prompts) * 3
    done    = 0

    QUERY_FNS = [
        ("ChatGPT", query_chatgpt),
        ("Gemini",  query_gemini),
        ("Claude",  query_claude),
    ]

    try:
        # Try playwright_stealth if available
        try:
            from playwright_stealth import stealth_async
            STEALTH = True
        except ImportError:
            STEALTH = False

        async with async_playwright() as pw:
            for model_name, query_fn in QUERY_FNS:
                log(f"\n{'─'*40}")
                log(f"🤖 Starting {model_name} browser session …")
                browser = None
                try:
                    browser = await pw.chromium.launch(
                        headless=True,
                        args=[
                            "--no-sandbox", "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage", "--disable-gpu",
                            "--disable-blink-features=AutomationControlled",
                            "--window-size=1280,800",
                        ]
                    )
                    context = await browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport={"width": 1280, "height": 800},
                        locale="en-US",
                        timezone_id="America/New_York",
                        extra_http_headers={
                            "Accept-Language": "en-US,en;q=0.9",
                            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24"',
                        }
                    )

                    # Apply stealth patches to context
                    if STEALTH:
                        page_test = await context.new_page()
                        try:
                            await stealth_async(page_test)
                        except Exception:
                            pass
                        await page_test.close()

                    for i, prompt in enumerate(prompts):
                        log(f"  [{model_name}] {i+1}/{len(prompts)}: {prompt[:65]}…")
                        try:
                            res = await query_fn(context, prompt)
                            res["brand"]       = brand
                            res["domain"]      = domain
                            res["competitors"] = competitors
                            results.append(res)

                            # Log outcome briefly
                            if res.get("error") == "login_required":
                                log(f"  ⚠️  Login wall hit — marking as login_required")
                            elif res.get("error"):
                                log(f"  ⚠️  Error: {res['error'][:80]}")
                            else:
                                preview = res["response"][:60].replace("\n"," ")
                                log(f"  ✅ Got {len(res['response'])} chars: "{preview}…"")

                        except Exception as e:
                            log(f"  ❌ Unexpected error on prompt {i+1}: {e}")
                            results.append({
                                "model": model_name, "prompt": prompt,
                                "response": f"[Error: {e}]", "sources": [],
                                "mock": False, "error": str(e),
                                "brand": brand, "domain": domain,
                                "competitors": competitors,
                            })

                        done += 1
                        progress_cb(done / total)

                        # Polite delay between prompts
                        if i < len(prompts) - 1:
                            delay = random.uniform(6, 12)
                            log(f"  ⏳ Waiting {delay:.1f}s …")
                            await asyncio.sleep(delay)

                except Exception as e:
                    log(f"❌ {model_name} browser launch failed: {e}")
                    # Fill remaining with errors
                    for p in prompts[len([r for r in results if r['model']==model_name]):]:
                        results.append({
                            "model": model_name, "prompt": p,
                            "response": f"[Browser launch failed: {e}]",
                            "sources": [], "mock": False, "error": str(e),
                            "brand": brand, "domain": domain,
                            "competitors": competitors,
                        })
                        done += 1
                        progress_cb(done / total)
                finally:
                    if browser:
                        await browser.close()

    except Exception as e:
        log(f"❌ Playwright runtime error: {e}")
        return []

    return results

