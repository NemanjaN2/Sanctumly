"""
Web search service
Primary: Serper.dev (Google Search API)
Fallback: DuckDuckGo
ADDED: fetch_url() and extract_urls() for reading links users share
"""
import logging
import os
import re
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

DDGS_AVAILABLE = False
try:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    pass

BS4_AVAILABLE = False
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    pass

MAX_PAGE_CONTENT = 4000

BLOCKED_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "tiktok.com", "linkedin.com", "reddit.com",
    "netflix.com", "spotify.com",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def extract_urls(text: str) -> list:
    """Extract all URLs from a message."""
    pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
    return re.findall(pattern, text)


def is_blocked_domain(url: str) -> bool:
    """Check if URL belongs to a blocked domain."""
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
        return any(blocked in domain for blocked in BLOCKED_DOMAINS)
    except Exception:
        return False


def clean_html(html: str) -> str:
    """Extract readable text from HTML."""
    if BS4_AVAILABLE:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header",
                         "aside", "form", "button", "iframe",
                         "noscript", "meta", "link"]):
            tag.decompose()
        main = (
            soup.find("article") or
            soup.find("main") or
            soup.find(attrs={"role": "main"}) or
            soup.find(id=re.compile(r"content|main|article", re.I)) or
            soup.find("body")
        )
        text = main.get_text(separator="\n") if main else soup.get_text(separator="\n")
    else:
        text = re.sub(r'<[^>]+>', ' ', html)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = [line for line in lines if len(line) > 30]
    return "\n".join(lines)


def fetch_url(url: str) -> str:
    """
    Fetch and extract readable content from a URL.
    Returns formatted string for context injection, or empty string on failure.
    """
    if is_blocked_domain(url):
        logger.info(f"Blocked domain, skipping fetch: {url}")
        return f"[URL blocked] {url} requires login or is a restricted platform."

    try:
        logger.info(f"Fetching URL: {url}")
        response = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)

        if response.status_code != 200:
            logger.warning(f"URL fetch returned {response.status_code}: {url}")
            return ""

        content_type = response.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            try:
                data = response.json()
                text = str(data)[:MAX_PAGE_CONTENT]
                return f"[Content from {url}]\n{text}\n"
            except Exception:
                pass

        if "text/html" not in content_type and "text/plain" not in content_type:
            logger.warning(f"Unsupported content type: {content_type}")
            return f"[Could not read content from {url} — unsupported format]"

        raw_text = clean_html(response.text)

        if not raw_text.strip():
            return ""

        if len(raw_text) > MAX_PAGE_CONTENT:
            raw_text = raw_text[:MAX_PAGE_CONTENT] + "\n... [content truncated]"

        domain = urlparse(url).netloc.replace("www.", "")
        logger.info(f"Fetched {len(raw_text)} chars from {domain}")
        return f"[Content from {domain}]\n{raw_text}\n"

    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching: {url}")
        return f"[Timeout] Could not load {url} — page took too long to respond."
    except requests.exceptions.ConnectionError:
        logger.error(f"Connection error fetching: {url}")
        return f"[Error] Could not connect to {url}."
    except Exception as e:
        logger.error(f"URL fetch error for {url}: {e}")
        return ""


def search_serper(query: str, max_results: int = 5) -> str:
    """Search using Serper.dev (Google Search API)"""
    if not SERPER_API_KEY:
        logger.warning("No SERPER_API_KEY set")
        return ""

    try:
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {"q": query, "num": max_results}

        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=10
        )

        if response.status_code != 200:
            logger.error(f"Serper error: {response.status_code} - {response.text[:200]}")
            return ""

        data = response.json()
        organic = data.get("organic", [])
        knowledge = data.get("knowledgeGraph", {})
        answer_box = data.get("answerBox", {})

        if not organic and not knowledge and not answer_box:
            logger.warning(f"Serper: No results for '{query}'")
            return ""

        search_text = ""

        if answer_box:
            ab_title = answer_box.get("title", "")
            ab_answer = answer_box.get("answer", answer_box.get("snippet", ""))
            if ab_answer:
                search_text += f"[Direct Answer] {ab_title}\n{ab_answer}\n\n"

        if knowledge:
            kg_title = knowledge.get("title", "")
            kg_desc = knowledge.get("description", "")
            kg_attrs = knowledge.get("attributes", {})
            if kg_title or kg_desc:
                search_text += f"[Knowledge] {kg_title}\n{kg_desc}\n"
                for key, val in kg_attrs.items():
                    search_text += f"  {key}: {val}\n"
                search_text += "\n"

        for i, result in enumerate(organic[:max_results], 1):
            title = result.get("title", "No title")
            snippet = result.get("snippet", "No description")
            link = result.get("link", "")
            search_text += f"[Result {i}] {title}\n"
            search_text += f"{snippet}\n"
            if link:
                search_text += f"Source: {link}\n"
            search_text += "\n"

        logger.info(f"Serper: Found {len(organic)} results for '{query}'")
        return search_text

    except requests.exceptions.Timeout:
        logger.error(f"Serper timeout for: '{query}'")
        return ""
    except Exception as e:
        logger.error(f"Serper error: {e}")
        return ""


def search_ddg(query: str, max_results: int = 5) -> str:
    """Fallback: Search using DuckDuckGo"""
    if not DDGS_AVAILABLE:
        return ""

    try:
        clean_query = query[:100] if len(query) > 100 else query
        logger.info(f"DuckDuckGo fallback searching for: '{clean_query}'")

        with DDGS() as ddgs:
            results = list(ddgs.text(clean_query, max_results=max_results, region='wt-wt', safesearch='off', timelimit='m'))

        if not results:
            return ""

        search_text = ""
        for i, result in enumerate(results, 1):
            title = result.get('title', 'No title')
            body = result.get('body', 'No description')
            url = result.get('href', '')
            search_text += f"[Result {i}] {title}\n"
            search_text += f"{body}\n"
            if url:
                search_text += f"Source: {url}\n"
            search_text += "\n"

        logger.info(f"DuckDuckGo: Found {len(results)} results")
        return search_text

    except Exception as e:
        logger.error(f"DuckDuckGo error: {e}")
        return ""


def search_web(query: str) -> str:
    """
    Search the web. Tries Serper (Google) first, falls back to DuckDuckGo.
    Returns formatted search results string, or empty string if both fail.
    """
    if SERPER_API_KEY:
        result = search_serper(query)
        if result:
            return result
        logger.info("Serper returned nothing, trying DuckDuckGo fallback...")

    result = search_ddg(query)
    if result:
        return result

    logger.warning(f"All search engines failed for: '{query}'")
    return ""
