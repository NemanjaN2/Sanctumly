"""
Web search service
Primary: Serper.dev (Google Search API)
Fallback: DuckDuckGo
ADDED: fetch_url() and extract_urls() for reading links users share
"""
import logging
import os
import re
import json
import requests
import socket
import ipaddress
from urllib.parse import urlparse, urljoin

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

MAX_PAGE_CONTENT = int(os.environ.get("MAX_PAGE_CONTENT", "3000"))
CREATOR_MAX_PAGE_CONTENT = 4000  # original limit, kept for the creator
SEARCH_MAX_RESULTS = int(os.environ.get("SEARCH_MAX_RESULTS", "3"))

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
        domain = (urlparse(url).hostname or "").lower().rstrip(".")
        if domain.startswith("www."):
            domain = domain[4:]
        return any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_DOMAINS)
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


def _validate_public_http_url(url: str) -> bool:
    """Reject non-HTTP schemes, local names and any host resolving to non-public IPs."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return False
        if parsed.username or parsed.password:
            return False
        hostname = parsed.hostname.rstrip(".").lower()
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith((".local", ".internal", ".lan")):
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_global
        except ValueError:
            pass
        results = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not results:
            return False
        return all(ipaddress.ip_address(item[4][0]).is_global for item in results)
    except Exception:
        return False


def fetch_url(url: str, is_creator: bool = False) -> str:
    """Fetch readable public web content without following redirects into private networks."""
    max_chars = CREATOR_MAX_PAGE_CONTENT if is_creator else MAX_PAGE_CONTENT
    if is_blocked_domain(url):
        logger.info("Blocked domain, skipping fetch: %s", url)
        return f"[URL blocked] {url} requires login or is a restricted platform."

    current_url = url
    session = requests.Session()
    session.trust_env = False
    try:
        for _ in range(4):
            if not _validate_public_http_url(current_url):
                logger.warning("Blocked non-public URL destination: %s", current_url)
                return "[URL blocked] The destination is not a public HTTP/HTTPS address."
            response = session.get(
                current_url, headers=HEADERS, timeout=(3, 8),
                allow_redirects=False, stream=True,
            )
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                response.close()
                if not location:
                    return ""
                current_url = urljoin(current_url, location)
                continue
            if response.status_code != 200:
                logger.warning("URL fetch returned %s: %s", response.status_code, current_url)
                response.close()
                return ""

            content_type = response.headers.get("content-type", "").lower()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > 1_000_000:
                response.close()
                return "[Could not read content from URL — page too large]"
            raw = bytearray()
            for part in response.iter_content(chunk_size=16384):
                if not part:
                    continue
                raw.extend(part)
                if len(raw) > 1_000_000:
                    response.close()
                    return "[Could not read content from URL — page too large]"
            encoding = response.encoding or "utf-8"
            response.close()

            if "application/json" in content_type:
                try:
                    data = json.loads(raw.decode(encoding, errors="replace"))
                    return f"[Content from {current_url}]\n{str(data)[:max_chars]}\n"
                except Exception:
                    return ""
            if "text/html" not in content_type and "text/plain" not in content_type:
                return "[Could not read content from URL — unsupported format]"

            raw_text = clean_html(raw.decode(encoding, errors="replace"))
            if not raw_text.strip():
                return ""
            if len(raw_text) > max_chars:
                raw_text = raw_text[:max_chars] + "\n... [content truncated]"
            domain = urlparse(current_url).netloc.replace("www.", "")
            logger.info("Fetched %s chars from %s", len(raw_text), domain)
            return f"[Content from {domain}]\n{raw_text}\n"

        return "[Could not read content from URL — too many redirects]"
    except requests.exceptions.Timeout:
        logger.warning("URL fetch timed out: %s", url)
        return f"[Timeout] Could not load {url} — page took too long to respond."
    except requests.exceptions.RequestException as exc:
        logger.warning("URL fetch failed (%s): %s", type(exc).__name__, url)
        return f"[Error] Could not connect to {url}."
    except Exception:
        logger.exception("Unexpected URL fetch error")
        return ""
    finally:
        session.close()


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


def search_web(query: str, is_creator: bool = False) -> str:
    """
    Search the web. Tries Serper (Google) first, falls back to DuckDuckGo.
    Returns formatted search results string, or empty string if both fail.
    """
    if SERPER_API_KEY:
        result = search_serper(query, 5 if is_creator else SEARCH_MAX_RESULTS)
        if result:
            return result
        logger.info("Serper returned nothing, trying DuckDuckGo fallback...")

    result = search_ddg(query, 5 if is_creator else SEARCH_MAX_RESULTS)
    if result:
        return result

    logger.warning(f"All search engines failed for: '{query}'")
    return ""
