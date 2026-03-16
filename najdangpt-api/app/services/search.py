"""
Web search service
Primary: Serper.dev (Google Search API) — 2,500 free queries, no credit card
Fallback: DuckDuckGo (if Serper fails or no API key)
"""
import logging
import os
import json
import requests

logger = logging.getLogger(__name__)

SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "")

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


def search_serper(query: str, max_results: int = 5) -> str:
    """Search using Serper.dev (Google Search API)"""
    if not SERPER_API_KEY:
        logger.warning("⚠️ No SERPER_API_KEY set")
        return ""
    
    try:
        headers = {
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "q": query,
            "num": max_results,
        }
        
        response = requests.post(
            "https://google.serper.dev/search",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Serper error: {response.status_code} - {response.text[:200]}")
            return ""
        
        data = response.json()
        
        # Build results from organic results
        organic = data.get("organic", [])
        knowledge = data.get("knowledgeGraph", {})
        answer_box = data.get("answerBox", {})
        
        if not organic and not knowledge and not answer_box:
            logger.warning(f"⚠️ Serper: No results for '{query}'")
            return ""
        
        search_text = ""
        
        # Include answer box if present (direct answer from Google)
        if answer_box:
            ab_title = answer_box.get("title", "")
            ab_answer = answer_box.get("answer", answer_box.get("snippet", ""))
            if ab_answer:
                search_text += f"[Direct Answer] {ab_title}\n{ab_answer}\n\n"
        
        # Include knowledge graph if present
        if knowledge:
            kg_title = knowledge.get("title", "")
            kg_desc = knowledge.get("description", "")
            kg_attrs = knowledge.get("attributes", {})
            if kg_title or kg_desc:
                search_text += f"[Knowledge] {kg_title}\n{kg_desc}\n"
                for key, val in kg_attrs.items():
                    search_text += f"  {key}: {val}\n"
                search_text += "\n"
        
        # Include organic results
        for i, result in enumerate(organic[:max_results], 1):
            title = result.get("title", "No title")
            snippet = result.get("snippet", "No description")
            link = result.get("link", "")
            
            search_text += f"[Result {i}] {title}\n"
            search_text += f"{snippet}\n"
            if link:
                search_text += f"Source: {link}\n"
            search_text += "\n"
        
        logger.info(f"✅ Serper: Found {len(organic)} results for '{query}'")
        return search_text
    
    except requests.exceptions.Timeout:
        logger.error(f"❌ Serper timeout for: '{query}'")
        return ""
    except Exception as e:
        logger.error(f"❌ Serper error: {e}")
        return ""


def search_ddg(query: str, max_results: int = 5) -> str:
    """Fallback: Search using DuckDuckGo"""
    if not DDGS_AVAILABLE:
        return ""
    
    try:
        clean_query = query
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
    Search the web. Tries Serper (Google) first, falls back to DuckDuckGo.
    Returns formatted search results string, or empty string if both fail.
    """
    # Try Serper first
    if SERPER_API_KEY:
        result = search_serper(query)
        if result:
            return result
        logger.info("⚠️ Serper returned nothing, trying DuckDuckGo fallback...")
    
    # Fallback to DuckDuckGo
    result = search_ddg(query)
    if result:
        return result
    
    logger.warning(f"⚠️ All search engines failed for: '{query}'")
    return ""
