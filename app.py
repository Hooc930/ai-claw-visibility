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
DB_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyses.db")
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
    log(f"🌐 Crawling {url} ...")
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
        log("🤖 Using Bedrock Claude Haiku for prompt generation ...")
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
                log(f"🤖 Starting {model_name} browser session ...")
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
                        log(f"  [{model_name}] {i+1}/{len(prompts)}: {prompt[:65]}...")
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
                                log(f"  OK Got {len(res['response'])} chars: {preview[:60]}")

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
                            log(f"  ⏳ Waiting {delay:.1f}s ...")
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


# ╔══════════════════════════════════════════════════════════════╗
# ║  STEP C — PARSING ENGINE                                    ║
# ╚══════════════════════════════════════════════════════════════╝
def extract_urls(text: str) -> list:
    pat = re.compile(r'https?://[^\s\)\]\>\"\'<]+(?:[^\s\.\,\)\]\>\"\':<]*[^\s\.\,\)\]\>\"\':<:])')
    return pat.findall(text)

def url_to_domain(url: str) -> str:
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""

def categorize(domain: str) -> str:
    for k, v in SOURCE_CATEGORIES.items():
        if k in domain:
            return v
    return "Other"

def sentiment_for(text: str, brand: str) -> tuple[str, float]:
    """TextBlob sentence-level sentiment on brand-mentioning sentences."""
    if not HAS_TEXTBLOB or not text:
        return "neutral", 0.5
    try:
        blob   = TextBlob(text)
        bl     = brand.lower()
        sents  = [s for s in blob.sentences if bl in str(s).lower()]
        if not sents:
            return "neutral", 0.5
        avg = sum(s.sentiment.polarity for s in sents) / len(sents)
        if avg > 0.08:
            return "positive", avg
        if avg < -0.08:
            return "negative", avg
        return "neutral", avg
    except Exception:
        return "neutral", 0.5

def parse_one(raw: dict) -> dict:
    brand       = raw.get("brand", "")
    domain      = raw.get("domain", "")
    response    = raw.get("response", "")
    src_urls    = raw.get("sources", [])
    competitors = raw.get("competitors", [])

    rl = response.lower()
    bl = brand.lower()

    brand_mentioned = bl in rl or (domain and domain in rl)

    # First-mention position: count distinct "other brands" before brand appears
    first_pos = 0
    if brand_mentioned:
        idx = rl.find(bl)
        if idx == -1 and domain:
            idx = rl.find(domain)
        pre = rl[:idx]
        GENERIC = ["hubspot","salesforce","notion","monday","asana","slack",
                   "zoom","shopify","mailchimp","google","microsoft","apple"]
        comp_set = set(c.lower() for c in competitors) | set(GENERIC)
        before   = sum(1 for c in comp_set if c != bl and c in pre)
        first_pos = before + 1      # 1-indexed

    sentiment, sent_score = sentiment_for(response, brand)

    all_urls     = extract_urls(response) + [u for u in src_urls if u.startswith("http")]
    cited_domains = list(dict.fromkeys(url_to_domain(u) for u in all_urls if url_to_domain(u)))

    # Competitor mentions in response
    comp_hits = []
    EXTRA = ["HubSpot","Salesforce","Mailchimp","Shopify","WordPress","Notion",
             "Monday","Asana","Slack","Google","Microsoft","Apple","Amazon",
             "Semrush","Ahrefs","Hotjar","Mixpanel","Amplitude","Figma","Canva",
             "Intercom","Zendesk","Freshdesk","Jira","ClickUp","Linear"]
    for c in list(competitors) + EXTRA:
        if c.lower() != bl and c.lower() in rl and c not in comp_hits:
            comp_hits.append(c)
    comp_hits = comp_hits[:8]

    own_cited = domain in cited_domains if domain else False

    return {
        "model":             raw.get("model"),
        "prompt":            raw.get("prompt"),
        "response":          response,
        "mock":              raw.get("mock", True),
        "error":             raw.get("error"),
        "brand_mentioned":   brand_mentioned,
        "first_pos":         first_pos,
        "sentiment":         sentiment,
        "sent_score":        sent_score,
        "cited_domains":     cited_domains,
        "source_cats":       {d: categorize(d) for d in cited_domains},
        "comp_mentions":     comp_hits,
        "own_cited":         own_cited,
        "brand":             brand,
        "domain":            domain,
    }


# ╔══════════════════════════════════════════════════════════════╗
# ║  STEP D — METRICS & SCORING                                 ║
# ╚══════════════════════════════════════════════════════════════╝
def compute_metrics(parsed: list) -> dict:
    if not parsed:
        return {}

    brand  = parsed[0]["brand"]
    domain = parsed[0]["domain"]
    total  = len(parsed)

    ment   = [r for r in parsed if r["brand_mentioned"]]
    vis    = len(ment) / total * 100

    positions = [r["first_pos"] for r in ment if r["first_pos"] > 0]
    avg_pos   = sum(positions) / len(positions) if positions else 5.0

    sents     = [r["sentiment"] for r in ment]
    n_pos     = sents.count("positive")
    n_neu     = sents.count("neutral")
    n_neg     = sents.count("negative")
    n_tot     = len(sents)
    sent_score = (n_pos * 1.0 + n_neu * 0.5) / n_tot if n_tot else 0.5

    own_count = sum(1 for r in parsed if r["own_cited"])
    own_pct   = own_count / total * 100

    all_cited = []
    for r in parsed:
        all_cited.extend(r["cited_domains"])
    cit_rate = len(all_cited) / total

    # Overall score
    score = min(100, max(0,
        0.40 * vis +
        0.20 * max(0, 100 - avg_pos * 5) +
        0.20 * sent_score * 100 +
        0.20 * own_pct
    ))

    # Per-model
    per_model = {}
    for model in MODELS:
        mr = [r for r in parsed if r["model"] == model]
        if not mr: continue
        mt = len(mr)
        mm = [r for r in mr if r["brand_mentioned"]]
        mv = len(mm) / mt * 100
        mp = [r["first_pos"] for r in mm if r["first_pos"] > 0]
        ma = sum(mp) / len(mp) if mp else 5.0
        ms = [r["sentiment"] for r in mm]
        mss = ((ms.count("positive") * 1.0 + ms.count("neutral") * 0.5) / len(ms)) if ms else 0.5
        mc = []; [mc.extend(r["cited_domains"]) for r in mr]
        mown = sum(1 for r in mr if r["own_cited"]) / mt * 100
        per_model[model] = {
            "total": mt, "mentioned": len(mm), "visibility_pct": mv,
            "avg_pos": ma, "sent_score": mss, "own_pct": mown,
            "cit_rate": len(mc)/mt, "cited_domains": mc,
            "pos": ms.count("positive"), "neu": ms.count("neutral"),
            "neg": ms.count("negative"), "results": mr,
        }

    # Top domains & competitors
    dom_counts  = Counter(all_cited)
    top_domains = [{"domain": d, "count": c, "category": categorize(d)}
                   for d, c in dom_counts.most_common(20)]

    all_comps = []
    for r in parsed: all_comps.extend(r["comp_mentions"])
    comp_counts = Counter(all_comps)
    top_comps   = [{"brand": b, "count": c}
                   for b, c in comp_counts.most_common(10)
                   if b.lower() != brand.lower()]

    # Login-wall stats
    login_count = sum(1 for r in parsed if r.get("error") == "login_required")
    error_count = sum(1 for r in parsed if r.get("error") and r.get("error") != "login_required")
    mock_count  = sum(1 for r in parsed if r.get("mock"))

    return {
        "brand": brand, "domain": domain, "total_queries": total,
        "visibility_pct": vis, "avg_pos": avg_pos, "sent_score": sent_score,
        "own_pct": own_pct, "cit_rate": cit_rate, "score": score,
        "n_pos": n_pos, "n_neu": n_neu, "n_neg": n_neg,
        "per_model": per_model, "top_domains": top_domains,
        "top_comps": top_comps, "parsed": parsed,
        "login_count": login_count, "error_count": error_count,
        "mock_count": mock_count,
    }

def score_band(s: float) -> tuple[str, str, str]:
    """Returns (emoji, hex_color, label)."""
    if s >= 71: return "🟢", "#22c55e", "Strong"
    if s >= 41: return "🟡", "#f59e0b", "Moderate"
    return "🔴", "#ef4444", "Critical"


# ╔══════════════════════════════════════════════════════════════╗
# ║  CHARTS                                                      ║
# ╚══════════════════════════════════════════════════════════════╝
DARK_BG  = "#0a0a0f"
CARD_BG  = "#111118"
GRID_COL = "#1e3a5f"
TEXT_COL = "#e2e8f0"
MUTED    = "#64748b"

def _base_layout(**kw):
    return dict(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font={"color": TEXT_COL, "family": "DM Sans"},
        margin={"l":20,"r":20,"t":44,"b":16},
        **kw
    )

def chart_gauge(score: float) -> go.Figure:
    _, color, label = score_band(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x":[0,1],"y":[0,1]},
        title={"text": f"Brand Visibility Score — {label}",
               "font": {"size":15, "color": TEXT_COL}},
        number={"font": {"size":52, "color": color, "family":"Space Mono"}, "suffix":""},
        gauge={
            "axis": {"range":[0,100], "tickwidth":1, "tickcolor":GRID_COL,
                     "tickfont":{"color": MUTED}},
            "bar":  {"color": color, "thickness":0.28},
            "bgcolor": CARD_BG, "borderwidth": 0,
            "steps": [
                {"range":[0,40],   "color":"#1f0d0d"},
                {"range":[40,70],  "color":"#1f1a0d"},
                {"range":[70,100], "color":"#0d1f0d"},
            ],
            "threshold":{"line":{"color":color,"width":3},
                         "thickness":0.85,"value":score},
        }
    ))
    fig.update_layout(**_base_layout(height=290))
    return fig

def chart_model_bars(per_model: dict) -> go.Figure:
    models = [m for m in MODELS if m in per_model]
    vis    = [per_model[m]["visibility_pct"] for m in models]
    cols   = [MODEL_COLORS[m] for m in models]
    fig = go.Figure(go.Bar(
        x=models, y=vis, marker_color=cols,
        text=[f"{v:.0f}%" for v in vis],
        textposition="outside", textfont={"color": TEXT_COL},
        width=0.45,
    ))
    fig.update_layout(
        **_base_layout(height=270),
        title={"text":"Visibility % by AI Model","font":{"color":TEXT_COL,"size":13}},
        xaxis={"tickfont":{"color":TEXT_COL},"gridcolor":GRID_COL},
        yaxis={"range":[0,115],"tickfont":{"color":TEXT_COL},"gridcolor":GRID_COL},
    )
    return fig

def chart_sentiment_pie(pos, neu, neg, model: str) -> go.Figure:
    mc = MODEL_COLORS.get(model,"#3b82f6")
    pairs = [("Positive",pos,"#22c55e"),("Neutral",neu,mc),("Negative",neg,"#ef4444")]
    lbl, val, clr = zip(*[(l,v,c) for l,v,c in pairs if v>0]) if any(v for _,v,_ in pairs) \
                    else (["No mentions"],[1],[GRID_COL])
    fig = go.Figure(go.Pie(
        labels=lbl, values=val, marker_colors=clr,
        hole=0.5, textfont={"color":TEXT_COL},
        hovertemplate="%{label}: %{value}<extra></extra>",
    ))
    fig.update_layout(
        **_base_layout(height=220, margin={"l":10,"r":10,"t":20,"b":10}),
        showlegend=True,
        legend={"font":{"color":TEXT_COL},"bgcolor":CARD_BG,"x":0.82,"y":0.5},
    )
    return fig

def chart_sources_bar(top_domains: list) -> go.Figure:
    top10  = top_domains[:10]
    doms   = [d["domain"] for d in top10]
    counts = [d["count"] for d in top10]
    fig = go.Figure(go.Bar(
        y=doms, x=counts, orientation="h",
        marker_color="#3b82f6",
        text=counts, textposition="outside",
        textfont={"color":TEXT_COL},
    ))
    fig.update_layout(
        **_base_layout(height=max(260, len(top10)*34+60)),
        title={"text":"Top Cited Domains","font":{"color":TEXT_COL,"size":13}},
        xaxis={"tickfont":{"color":TEXT_COL},"gridcolor":GRID_COL},
        yaxis={"tickfont":{"color":TEXT_COL,"size":11},"gridcolor":GRID_COL,
               "autorange":"reversed"},
    )
    return fig

def chart_competitor_bar(top_comps: list) -> go.Figure:
    top8 = top_comps[:8]
    fig = go.Figure(go.Bar(
        x=[c["brand"] for c in top8],
        y=[c["count"] for c in top8],
        marker_color="#ef4444",
        text=[c["count"] for c in top8],
        textposition="outside", textfont={"color":TEXT_COL},
        width=0.5,
    ))
    fig.update_layout(
        **_base_layout(height=260),
        title={"text":"Competitor Mentions in AI Responses","font":{"color":TEXT_COL,"size":13}},
        xaxis={"tickfont":{"color":TEXT_COL}},
        yaxis={"tickfont":{"color":TEXT_COL},"gridcolor":GRID_COL},
    )
    return fig


# ╔══════════════════════════════════════════════════════════════╗
# ║  REPORT TABS                                                 ║
# ╚══════════════════════════════════════════════════════════════╝

# ── Tab 1: Executive Summary ──────────────────────────────────────────────────
def tab_executive(m: dict):
    brand = m["brand"]
    score = m["score"]
    emoji, color, label = score_band(score)

    col_gauge, col_insight = st.columns([1,1], gap="large")

    with col_gauge:
        st.plotly_chart(chart_gauge(score), use_container_width=True)
        c1, c2 = st.columns(2)
        with c1:
            delta_vis = f"+{m['visibility_pct']-50:.0f}%" if m['visibility_pct']>50 else f"{m['visibility_pct']-50:.0f}%"
            st.metric("Visibility", f"{m['visibility_pct']:.0f}%", delta=delta_vis,
                      help="% of AI responses that mention the brand")
            st.metric("Avg Position", f"#{m['avg_pos']:.1f}",
                      help="Average rank of first brand mention (1=first mentioned brand)")
        with c2:
            st.metric("Sentiment", f"{m['sent_score']*100:.0f}/100",
                      help="Weighted sentiment score (positive=100, neutral=50, negative=0)")
            st.metric("Own Site Cited", f"{m['own_pct']:.0f}%",
                      help="% of responses that include a link to your domain")

        # Data quality callout
        if m.get("login_count",0) > 0 or m.get("mock_count",0) > 0:
            n_live = m["total_queries"] - m.get("mock_count",0) - m.get("login_count",0)
            n_wall = m.get("login_count",0)
            n_mock = m.get("mock_count",0)
            wall_part = f' · <b style="color:#f59e0b">{n_wall} login-wall</b>' if n_wall else ""
            mock_part = f' · <b style="color:#64748b">{n_mock} mock</b>' if n_mock else ""
            dq_html = (
                '<div style="background:#0d1729;border:1px solid #1e3a5f;border-radius:8px;'
                'padding:.7rem .9rem;font-size:.78rem;color:#94a3b8;margin-top:.5rem;">'
                f'Data: <b style="color:#22c55e">{n_live} live</b>'
                f'{wall_part}{mock_part}'
                f' out of {m["total_queries"]} queries</div>'
            )
            st.markdown(dq_html, unsafe_allow_html=True)

    with col_insight:
        st.markdown("#### 💡 Top Insights")
        insights = _gen_insights(m)
        for ins in insights:
            st.markdown(f'<div class="insight">{ins}</div>', unsafe_allow_html=True)

        if m.get("per_model"):
            st.markdown("#### 📊 Model Comparison")
            st.plotly_chart(chart_model_bars(m["per_model"]), use_container_width=True)

    st.info("⏰ Point-in-time snapshot — AI responses vary daily. Run regularly to track trends.")


def _gen_insights(m: dict) -> list:
    brand = m["brand"]
    vis   = m["visibility_pct"]
    score = m["score"]
    out   = []

    if m.get("per_model"):
        best  = max(m["per_model"], key=lambda x: m["per_model"][x]["visibility_pct"])
        worst = min(m["per_model"], key=lambda x: m["per_model"][x]["visibility_pct"])
        bv    = m["per_model"][best]["visibility_pct"]
        wv    = m["per_model"][worst]["visibility_pct"]

    # Visibility insight
    if vis >= 70:
        out.append(f"✅ <b>Strong AI presence</b> — {brand} appears in {vis:.0f}% of AI responses, above average.")
    elif vis >= 40:
        out.append(f"⚡ <b>Moderate visibility</b> — {brand} appears in {vis:.0f}% of AI responses. Real growth opportunity.")
    else:
        out.append(f"🚨 <b>Low AI visibility</b> — {brand} appears in only {vis:.0f}% of responses. Immediate action needed.")

    # Model spread insight
    if m.get("per_model") and len(m["per_model"]) > 1:
        if bv - wv > 25:
            out.append(f"📊 <b>Uneven model coverage</b> — {best} shows {bv:.0f}% vs {worst} only {wv:.0f}%. "
                       f"Optimise for {worst} specifically.")
        else:
            out.append(f"📊 <b>Consistent across models</b> — {best} leads at {bv:.0f}%, {worst} trails at {wv:.0f}%. "
                       f"Solid baseline across all three AI platforms.")

    # Competitor / own-site insight
    if m["top_comps"]:
        tc = m["top_comps"][0]
        out.append(f"🏆 <b>Top AI competitor: {tc['brand']}</b> — mentioned {tc['count']}× across responses. "
                   f"Create a '{brand} vs {tc['brand']}' comparison page to capture this traffic.")
    elif m["own_pct"] < 15:
        out.append(f"📎 <b>Own domain rarely cited</b> — only {m['own_pct']:.0f}% of responses include a link to {m['domain']}. "
                   f"Improve domain authority and publish citation-worthy content.")

    return out[:3]


# ── Tab 2: Per-Model Deep Dive ────────────────────────────────────────────────
def tab_per_model(m: dict):
    brand = m["brand"]
    for model in MODELS:
        if model not in m.get("per_model", {}):
            st.warning(f"No data collected for {model}")
            continue
        d = m["per_model"][model]
        _, mc, _ = score_band(d["visibility_pct"])

        with st.expander(
            f"🤖 {model}  ·  {d['visibility_pct']:.0f}% Visibility  ·  "
            f"{d['mentioned']}/{d['total']} mentions",
            expanded=True
        ):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Visibility", f"{d['visibility_pct']:.0f}%")
            c2.metric("Avg Position", f"#{d['avg_pos']:.1f}")
            c3.metric("Sentiment", f"{d['sent_score']*100:.0f}/100")
            c4.metric("Own Site", f"{d['own_pct']:.0f}%")

            col_pie, col_src = st.columns([1,1])
            with col_pie:
                st.plotly_chart(chart_sentiment_pie(d["pos"],d["neu"],d["neg"],model),
                                use_container_width=True)
            with col_src:
                st.markdown("**Top Cited Sources**")
                dc = Counter(d["cited_domains"])
                if dc:
                    df_s = pd.DataFrame(
                        [{"Domain":dom,"Cited":cnt,"Category":categorize(dom)}
                         for dom,cnt in dc.most_common(6)]
                    )
                    st.dataframe(df_s, hide_index=True, use_container_width=True)
                else:
                    st.caption("No source URLs extracted")

            # Example wins / losses
            results = d.get("results", [])
            win  = next((r for r in results if r["brand_mentioned"] and not r.get("error")), None)
            lose = next((r for r in results if not r["brand_mentioned"] and not r.get("error")), None)

            col_w, col_l = st.columns(2)
            with col_w:
                st.markdown("**✅ Winning prompt** *(brand mentioned)*")
                if win:
                    st.caption(f"Prompt: _{win['prompt']}_")
                    badge = "🟡 Mock" if win.get("mock") else "🟢 Live"
                    st.caption(badge)
                    st.text_area("Response", win["response"][:700]+"...",
                                 height=160, key=f"win_{model}", disabled=True)
                else:
                    st.caption("None found")
            with col_l:
                st.markdown("**❌ Losing prompt** *(brand NOT mentioned)*")
                if lose:
                    st.caption(f"Prompt: _{lose['prompt']}_")
                    badge = "🟡 Mock" if lose.get("mock") else "🟢 Live"
                    st.caption(badge)
                    st.text_area("Response", lose["response"][:700]+"...",
                                 height=160, key=f"lose_{model}", disabled=True)
                else:
                    st.caption("Brand mentioned in all responses! 🎉")


# ── Tab 3: Sources & Citations ────────────────────────────────────────────────
def tab_sources(m: dict):
    st.markdown("### 🔗 Cited Sources Across All Responses")
    if m["top_domains"]:
        df = pd.DataFrame(m["top_domains"])
        df.columns = ["Domain","Times Cited","Category"]
        comp_domains = {c["brand"].lower().replace(" ","") for c in m["top_comps"]}
        df["Competitor?"] = df["Domain"].apply(
            lambda d: "⚠️ Yes" if any(c in d.replace("-","") for c in comp_domains) else "—"
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.plotly_chart(chart_sources_bar(m["top_domains"]), use_container_width=True)
    else:
        st.info("No source URLs were extracted from AI responses.")

    st.markdown("### 🏆 Competitor Brand Frequency")
    if m["top_comps"]:
        df2 = pd.DataFrame(m["top_comps"])
        df2.columns = ["Brand","Mentions"]
        df2["Mention Rate"] = (df2["Mentions"] / m["total_queries"] * 100).apply(lambda x: f"{x:.0f}%")
        c1, c2 = st.columns([1,1])
        with c1:
            st.dataframe(df2, use_container_width=True, hide_index=True)
        with c2:
            st.plotly_chart(chart_competitor_bar(m["top_comps"]), use_container_width=True)
    else:
        st.info("No competitor brands detected in responses.")


# ── Tab 4: Traffic & Visits ───────────────────────────────────────────────────
def tab_traffic(m: dict):
    vis   = m["visibility_pct"]
    brand = m["brand"]
    est   = int(vis / 100 * 50_000 * 0.08)

    st.markdown("### 🚀 Estimated AI-Referred Traffic")
    c1, c2, c3 = st.columns(3)
    c1.metric("Est. Monthly Visits", f"{est:,}", help="Visibility% × 50K AI queries/mo × 8% CTR")
    c2.metric("AI Visibility Rate", f"{vis:.0f}%")
    c3.metric("Annual Estimate", f"{est*12:,}")

    st.markdown("""
    <div class="card" style="margin-top:.8rem;">
    <div class="card-title">📐 Methodology</div>
    <p style="color:#94a3b8;font-size:.88rem;line-height:1.7;margin:0;">
    <b>Formula:</b> Visibility% × 50,000 (estimated monthly AI-assisted searches in your category) × 8% (avg click-through from AI answer to source site)<br>
    <b>Note:</b> Estimates only. Real traffic depends on category volume, response quality, and whether your brand appears with a clickable link.
    </p></div>
    """, unsafe_allow_html=True)

    st.markdown("### 📈 Per-Model Traffic Breakdown")
    if m.get("per_model"):
        cols = st.columns(len(m["per_model"]))
        for i,(model,d) in enumerate(m["per_model"].items()):
            mt = int(d["visibility_pct"]/100 * 50_000 * 0.08)
            cols[i].metric(f"{model}", f"{mt:,}/mo", delta=f"{d['visibility_pct']:.0f}% vis")

    with st.expander("📋 GA4 Setup Guide: Track AI Chat Referrals", expanded=False):
        st.markdown(f"""
### Tracking AI-Referred Traffic in Google Analytics 4

#### Step 1 — Custom Channel Group "AI Chat"
**Admin → Data Display → Channel Groups → New group**

Add these conditions (session source **contains**):
| Source | AI Platform |
|--------|-------------|
| `chatgpt.com` | ChatGPT |
| `claude.ai` | Claude |
| `gemini.google.com` | Gemini |
| `perplexity.ai` | Perplexity |
| `copilot.microsoft.com` | Copilot |

#### Step 2 — UTM-tag any links you publish
```
https://{m['domain']}?utm_source=ai-chat&utm_medium=organic&utm_campaign=ai-visibility
```

#### Step 3 — Check referrer traffic today
1. GA4 → **Reports → Acquisition → Traffic Acquisition**
2. Set primary dimension to **Session source / medium**
3. Filter: source contains `chatgpt.com` OR `claude.ai` OR `gemini.google.com`
4. Check **Realtime** for live AI-referred visitors

#### Step 4 — Set an Alert
GA4 → **Admin → Insights & Alerts** → Create alert when AI channel sessions > threshold

> **Attribution note:** Many AI-referred visits appear as "direct" traffic because some
> AI interfaces strip referrer headers. UTM parameters are essential for accurate tracking.
        """)


# ── Tab 5: Recommendations ────────────────────────────────────────────────────
def tab_recommendations(m: dict):
    brand = m["brand"]
    score = m["score"]
    vis   = m["visibility_pct"]
    emoji, color, label = score_band(score)

    if score < 40:
        st.error(f"🚨 **Critical — {brand} is nearly invisible to AI.**  Score: {score:.0f}/100")
    elif score < 70:
        st.warning(f"⚡ **Moderate visibility** — room to grow.  Score: {score:.0f}/100")
    else:
        st.success(f"✅ **Strong AI presence** — keep it up.  Score: {score:.0f}/100")

    comp_name = m["top_comps"][0]["brand"] if m["top_comps"] else "competitors"
    ed_sites  = [d["domain"] for d in m["top_domains"] if d["category"]=="Editorial"][:3]
    rev_sites = [d["domain"] for d in m["top_domains"] if d["category"]=="Review/UGC"][:3]

    recs = [
        {
            "pri":"high" if score<50 else "medium",
            "title":f"Build review presence on G2, Trustpilot & Capterra",
            "body":(
                f"Review platforms are the #1 most cited category in AI responses. "
                f"Getting {brand} listed with 50+ verified reviews on G2, Trustpilot, "
                f"and Capterra directly increases how often AI models mention you."
            ),
            "effort":"Medium","impact":"Very High",
        },
        {
            "pri":"high" if vis<50 else "medium",
            "title":f"Create '{brand} vs {comp_name}' comparison page",
            "body":(
                f"{comp_name} appears frequently in AI responses about your category. "
                f"A dedicated comparison page (/vs/{comp_name.lower().replace(' ','-')}) "
                f"is commonly cited by AI when users ask about alternatives. "
                f"Include a feature matrix, pricing table, and use-case breakdown."
            ),
            "effort":"Low","impact":"High",
        },
        {
            "pri":"medium",
            "title":f"Get featured on {ed_sites[0] if ed_sites else 'editorial sites'}",
            "body":(
                f"AI models heavily cite editorial sources like "
                f"{', '.join(ed_sites) if ed_sites else 'TechCrunch, Wired, Forbes'}. "
                f"Pitch product reviews, guest posts, or expert quotes. "
                f"A single feature on a top editorial site can meaningfully lift your score."
            ),
            "effort":"High","impact":"Very High",
        },
        {
            "pri":"medium",
            "title":"Add structured schema markup (JSON-LD)",
            "body":(
                f"Add Organization, Product, FAQ, and HowTo JSON-LD schema to your site. "
                f"This helps AI models understand {brand}'s identity, products, and use cases "
                f"more precisely — improving both mention accuracy and sentiment."
            ),
            "effort":"Low","impact":"Medium",
        },
        {
            "pri":"medium" if score>40 else "high",
            "title":"Publish high-intent answer pages",
            "body":(
                f"Create pages that directly answer: 'What is {brand}?', "
                f"'How does {brand} work?', '{brand} pricing', '{brand} alternatives'. "
                f"AI models surface well-structured answer content from authoritative domains."
            ),
            "effort":"Medium","impact":"High",
        },
        {
            "pri":"low",
            "title":f"Pursue a Wikipedia article for {brand}",
            "body":(
                f"Wikipedia is cited in nearly every AI response set we've seen. "
                f"If {brand} meets notability criteria, a Wikipedia article provides "
                f"a persistent, high-trust signal for all AI systems."
            ),
            "effort":"Medium","impact":"High",
        },
        {
            "pri":"low",
            "title":f"Monitor AI visibility weekly",
            "body":(
                f"AI responses change frequently as models are updated. "
                f"Run this tool at least weekly for {brand} to detect drops early. "
                f"Set a target score of {min(score+15,95):.0f} and track progress."
            ),
            "effort":"Low","impact":"Ongoing",
        },
    ]

    PRI_STYLES = {"high":"rec-high","medium":"rec-medium","low":"rec-low"}
    PRI_LABELS = {"high":"🔴 High Priority","medium":"🟡 Medium","low":"🟢 Nice-to-Have"}

    for rec in recs[:6]:
        cls = PRI_STYLES.get(rec["pri"],"rec-medium")
        with st.expander(f"{PRI_LABELS[rec['pri']]}  |  {rec['title']}"):
            col_body, col_meta = st.columns([3,1])
            with col_body:
                st.markdown(f'<div class="insight {cls}" style="margin:0;">{rec["body"]}</div>',
                            unsafe_allow_html=True)
            with col_meta:
                st.metric("Effort",rec["effort"])
                st.metric("Impact",rec["impact"])


# ── Tab 6: Raw Data ───────────────────────────────────────────────────────────
def tab_raw(m: dict):
    parsed = m.get("parsed",[])
    if not parsed:
        st.info("No data"); return

    st.markdown(f"### 📋 All {len(parsed)} Responses")
    rows = []
    for r in parsed:
        rows.append({
            "Model":             r["model"],
            "Prompt":            r["prompt"],
            "Mentioned":         "✅" if r["brand_mentioned"] else "❌",
            "Position":          r["first_pos"] if r["brand_mentioned"] else "—",
            "Sentiment":         r["sentiment"],
            "Sent Score":        f"{r['sent_score']:.2f}",
            "Sources":           len(r["cited_domains"]),
            "Own Site":          "✅" if r["own_cited"] else "❌",
            "Competitors":       ", ".join(r["comp_mentions"][:3]) or "—",
            "Data Type":         "🟡 Mock" if r.get("mock") else (
                                 "⚠️ Login" if r.get("error")=="login_required" else "🟢 Live"),
            "Response Preview":  r["response"][:120].replace("\n"," ")+"...",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    with c1:
        st.download_button("📥 Export CSV", df.to_csv(index=False),
            file_name=f"aiclaw_{m['brand']}_{ts}.csv", mime="text/csv")
    with c2:
        export = [{"model":r["model"],"prompt":r["prompt"],"response":r["response"],
                   "brand_mentioned":r["brand_mentioned"],"sentiment":r["sentiment"],
                   "cited_domains":r["cited_domains"],"competitors":r["comp_mentions"]}
                  for r in parsed]
        st.download_button("📥 Export JSON", json.dumps(export,indent=2),
            file_name=f"aiclaw_{m['brand']}_{ts}.json", mime="application/json")


# ╔══════════════════════════════════════════════════════════════╗
# ║  ANALYSIS RUNNER (sync wrapper)                             ║
# ╚══════════════════════════════════════════════════════════════╝
def run_analysis(url: str, brand_override: str, num_prompts: int,
                 use_browser: bool, log_lines: list,
                 progress_ph, status_ph) -> tuple[dict,dict]:

    def log(msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        log_lines.append(f"[{ts}] {msg}")
        html = "<br>".join(log_lines[-22:])
        status_ph.markdown(f'<div class="log-box">{html}</div>', unsafe_allow_html=True)

    def prog(v: float):
        progress_ph.progress(min(v, 1.0))

    # ── Step A ──
    prog(0.02)
    log("━━━ STEP A: Site Intelligence ━━━")
    intel = analyze_site(url, brand_override, num_prompts, log)
    brand       = intel["brand"]
    domain      = intel["domain"]
    prompts     = intel["prompts"]
    competitors = intel["competitors"]
    prog(0.08)

    # ── Step B ──
    raw_results = []
    log("━━━ STEP B: AI Model Queries ━━━")

    if use_browser and HAS_PLAYWRIGHT:
        log("🌐 Live browser mode — querying real AI UIs ...")
        log(f"⚠️  This takes ~{len(prompts)*3//6 + 3}–{len(prompts)*3//4 + 5} minutes. Please wait.")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            raw_results = loop.run_until_complete(
                run_live_queries(prompts, brand, domain, competitors, prog, log)
            )
            loop.close()
        except Exception as e:
            log(f"❌ Live query error: {e}")
            raw_results = []

        # Check if we got useful results; fall back if all errored
        live_ok = [r for r in raw_results if not r.get("error")]
        if not live_ok:
            log("⚠️  All live queries failed — falling back to mock mode")
            raw_results = []
    else:
        if not use_browser:
            log("🎭 Mock mode — generating simulated responses ...")
        elif not HAS_PLAYWRIGHT:
            log("⚠️  Playwright not installed — using mock mode")

    if not raw_results:
        for model in MODELS:
            for prompt in prompts:
                r = mock_response(model, prompt, brand, domain, competitors)
                r.update({"brand": brand, "domain": domain, "competitors": competitors})
                raw_results.append(r)
        prog(0.7)
        log(f"✅ Generated {len(raw_results)} mock responses")

    # ── Step C ──
    log("━━━ STEP C: Parsing & Sentiment ━━━")
    parsed = [parse_one(r) for r in raw_results]
    prog(0.88)

    # ── Step D ──
    log("━━━ STEP D: Scoring ━━━")
    metrics = compute_metrics(parsed)
    prog(1.0)

    emoji, _, label = score_band(metrics["score"])
    log(f"✅ Done! Score: {metrics['score']:.0f}/100 ({emoji} {label})")
    return metrics, intel


# ╔══════════════════════════════════════════════════════════════╗
# ║  MAIN UI                                                     ║
# ╚══════════════════════════════════════════════════════════════╝
def main():
    init_db()
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Hero ──────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero">
        <div class="hero-claw">⚡</div>
        <div>
            <div class="hero-logo">AI CLAW</div>
            <div class="hero-sub">Brand Visibility Analyzer · Real Browser Automation</div>
        </div>
        <div class="hero-badge">🌐 No API Keys Required</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### ⚙️ Analysis Settings")

        # No-API-key callout
        st.markdown("""
        <div class="sb-note">
        🌐 <b>No API keys needed</b><br>
        This tool uses real browser automation to visit ChatGPT, Gemini, and Claude — 
        exactly like a human user would. Zero API keys required.
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        url = st.text_input("🌐 Website URL *", placeholder="https://yourcompany.com")
        brand_input = st.text_input(
            "🏷️ Brand Name(s)",
            placeholder="Auto-detected from domain if blank",
        )
        country = st.selectbox(
            "🌍 Target Country",
            list(COUNTRIES.keys()),
            format_func=lambda k: f"{k} — {COUNTRIES[k]}",
        )
        num_prompts = st.slider("📝 Prompts per model", 5, 20, 12)

        st.markdown("---")
        st.markdown("#### 🤖 Query Mode")

        browser_ok   = HAS_PLAYWRIGHT
        browser_help = (
            "Launches headless Chromium to visit chatgpt.com, gemini.google.com, and claude.ai. "
            "Real responses — no API. May hit login walls on Claude/Gemini."
            if browser_ok else
            "⚠️ Playwright not installed. Install it to enable live browser mode."
        )
        use_browser = st.toggle(
            "🌐 Live Browser Scraping",
            value=False,
            disabled=not browser_ok,
            help=browser_help,
        )

        if use_browser:
            st.success("🟢 Live mode — real AI browser queries")
            with st.expander("ℹ️ Live mode notes"):
                st.markdown("""
                - **ChatGPT** — works without login for free queries
                - **Gemini** — may require Google login; will be marked if blocked
                - **Claude** — supports guest sessions without login
                - Runs headless Chromium; each prompt takes 30–60 seconds
                - Total time: ~5–15 minutes depending on prompt count
                - Login-wall results are flagged; score computed on available data
                """)
        else:
            st.info("🎭 Mock mode — instant demo with simulated responses")

        st.markdown("---")
        run_btn = st.button(
            "🔍 Run AI Visibility Analysis",
            use_container_width=True, type="primary"
        )

        st.markdown("---")
        st.markdown("#### 📂 Previous Analyses")
        recent = load_recent(5)
        if recent:
            opts = {"— New Analysis —": None}
            for row in recent:
                label = f"[{row[1][:10]}] {row[3]} — {row[4]:.0f}/100"
                opts[label] = row[0]
            sel = st.selectbox("Load", list(opts.keys()))
            if sel != "— New Analysis —" and st.button("📂 Load"):
                data = load_by_id(opts[sel])
                if data:
                    st.session_state["metrics"] = data.get("metrics")
                    st.session_state["intel"]   = data.get("intel")
                    st.success("✅ Loaded")
                    st.rerun()
        else:
            st.caption("No saved analyses yet")

    # ── Run ───────────────────────────────────────────────────────────────────
    if run_btn:
        if not url.strip():
            st.error("❌ Please enter a website URL"); st.stop()
        st.session_state.pop("metrics", None)
        st.session_state.pop("intel",   None)

        st.markdown("### 🔄 Analysis in progress ...")
        prog_ph   = st.progress(0)
        status_ph = st.empty()
        log_lines = []

        with st.spinner(""):
            try:
                metrics, intel = run_analysis(
                    url.strip(), brand_input.strip(), num_prompts,
                    use_browser, log_lines, prog_ph, status_ph
                )
                st.session_state["metrics"] = metrics
                st.session_state["intel"]   = intel
                save_analysis(url, metrics["brand"], metrics["score"],
                              {"metrics": metrics, "intel": intel})
                if metrics["score"] > 70:
                    st.balloons()
                st.success(f"✅ Complete — Score: {metrics['score']:.0f}/100")
                time.sleep(0.4)
                st.rerun()
            except Exception as e:
                st.error(f"❌ Analysis failed: {e}")
                st.code(traceback.format_exc())

    # ── Results ───────────────────────────────────────────────────────────────
    metrics = st.session_state.get("metrics")
    intel   = st.session_state.get("intel")

    if metrics:
        brand = metrics["brand"]
        score = metrics["score"]
        emoji, color, label = score_band(score)

        # Prompts expander
        if intel and intel.get("prompts"):
            with st.expander(f"📝 {len(intel['prompts'])} prompts used in analysis", expanded=False):
                for i, p in enumerate(intel["prompts"], 1):
                    st.markdown(f"**{i}.** {p}")

        # Tabs
        t1,t2,t3,t4,t5,t6 = st.tabs([
            "📊 Executive Summary",
            "🤖 Per-Model Deep Dive",
            "🔗 Sources & Citations",
            "🚀 Traffic & Visits",
            "💡 Recommendations",
            "📋 Raw Data",
        ])
        with t1: tab_executive(metrics)
        with t2: tab_per_model(metrics)
        with t3: tab_sources(metrics)
        with t4: tab_traffic(metrics)
        with t5: tab_recommendations(metrics)
        with t6: tab_raw(metrics)

    else:
        # Welcome / empty state
        st.markdown("""
        <div class="empty-state">
            <div class="empty-icon">⚡</div>
            <div class="empty-title">Discover how AI models talk about your brand</div>
            <div class="empty-sub">
                AI Claw visits ChatGPT, Gemini, and Claude using real browser automation —
                exactly like a human user — and measures how often your brand is mentioned,
                at what position, with what sentiment, and alongside which competitors.
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1,c2,c3 = st.columns(3)
        feats = [
            ("📊","Visibility Score","0–100 composite metric: mention rate, position, sentiment & citation strength."),
            ("🌐","Real Browser Data","Playwright visits actual AI chat UIs. No API. What real users see."),
            ("💡","Action Plan","Personalised recommendations to boost your AI presence, ranked by impact."),
        ]
        for col,(icon,title,desc) in zip([c1,c2,c3],feats):
            with col:
                st.markdown(f"""
                <div class="feature-card">
                    <div class="feature-icon">{icon}</div>
                    <div class="feature-title">{title}</div>
                    <div class="feature-desc">{desc}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("""
        <div class="empty-hint">
            ← Enter your website URL in the sidebar and click <b>🔍 Run AI Visibility Analysis</b>
        </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
