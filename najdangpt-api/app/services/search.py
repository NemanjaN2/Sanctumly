"""
Web search service
Primary: Brave Search API ($5 free credits/month ≈ 1000 queries)
Fallback: DuckDuckGo (if Brave fails or no API key)
"""
import logging
import os
import requests

logger = logging.getLogger(__name__)

BRAVE_API_KEY = os.environ.get("BRAVE_SEARCH_API_KEY", "")

# Try importing DuckDuckGo as fallback
DDGS_AVAILABLE = False
try:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        from ddgs import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    pass


def search_brave(query: str, max_results: int = 5) -> str:
    """Search using Brave Search API"""
    if not BRAVE_API_KEY:
        logger.warning("⚠️ No BRAVE_SEARCH_API_KEY set")
        return ""
    
    try:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": BRAVE_API_KEY,
        }
        params = {
            "q": query,
            "count": max_results,
            "text_decorations": False,
            "search_lang": "en",
        }
        
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Brave Search error: {response.status_code} - {response.text[:200]}")
            return ""
        
        data = response.json()
        results = data.get("web", {}).get("results", [])
        
        if not results:
            logger.warning(f"⚠️ Brave: No results for '{query}'")
            return ""
        
        search_text = ""
        for i, result in enumerate(results[:max_results], 1):
            title = result.get("title", "No title")
            description = result.get("description", "No description")
            url = result.get("url", "")
            
            search_text += f"[Result {i}] {title}\n"
            search_text += f"{description}\n"
            if url:
                search_text += f"Source: {url}\n"
            search_text += "\n"
        
        logger.info(f"✅ Brave Search: Found {len(results)} results for '{query}'")
        return search_text
    
    except requests.exceptions.Timeout:
        logger.error(f"❌ Brave Search timeout for: '{query}'")
        return ""
    except Exception as e:
        logger.error(f"❌ Brave Search error: {e}")
        return ""


def search_ddg(query: str, max_results: int = 5) -> str:
    """Fallback: Search using DuckDuckGo"""
    if not DDGS_AVAILABLE:
        return ""
    
    try:
        clean_query = query.lower()
        remove_words = ['search the web', 'search for', 'search', 'look up', 'find', 'what is', 'what are']
        for word in remove_words:
            clean_query = clean_query.replace(word, '')
        clean_query = clean_query.strip()
        
        if len(clean_query) > 100:
            clean_query = clean_query[:100]
        
        logger.info(f"🦆 DuckDuckGo fallback searching for: '{clean_query}'")
        
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
        
        logger.info(f"✅ DuckDuckGo: Found {len(results)} results")
        return search_text
    
    except Exception as e:
        logger.error(f"❌ DuckDuckGo error: {e}")
        return ""


def search_web(query: str) -> str:
    """
    Search the web. Tries Brave first, falls back to DuckDuckGo.
    Returns formatted search results string, or empty string if both fail.
    """
    # Try Brave first
    if BRAVE_API_KEY:
        result = search_brave(query)
        if result:
            return result
        logger.info("⚠️ Brave returned nothing, trying DuckDuckGo fallback...")
    
    # Fallback to DuckDuckGo
    result = search_ddg(query)
    if result:
        return result
    
    logger.warning(f"⚠️ All search engines failed for: '{query}'")
    return ""
