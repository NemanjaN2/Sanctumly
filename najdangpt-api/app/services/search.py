"""
Web search service using DuckDuckGo
"""

import logging

try:
    from duckduckgo_search import DDGS
except ImportError:
    from ddgs import DDGS

logger = logging.getLogger(__name__)


def search_web(query: str) -> str:
    """Search the web using DuckDuckGo"""
    try:
        # Clean up query
        clean_query = query.lower()
        remove_words = ['search the web', 'search for', 'search', 'look up', 'find', 'what is', 'what are']
        for word in remove_words:
            clean_query = clean_query.replace(word, '')
        clean_query = clean_query.strip()
        
        if len(clean_query) > 100:
            clean_query = clean_query[:100]
        
        logger.info(f"🔍 Searching for: '{clean_query}'")
        
        with DDGS() as ddgs:
            results = list(ddgs.text(clean_query, max_results=5, region='wt-wt', safesearch='off', timelimit='m'))
            
            if not results:
                logger.warning(f"⚠️ No results for: '{clean_query}'")
                return ""
            
            search_text = "🔍 **Web Search Results:**\n\n"
            for i, result in enumerate(results, 1):
                title = result.get('title', 'No title')
                body = result.get('body', 'No description')
                url = result.get('href', '')
                
                search_text += f"**{i}. {title}**\n"
                search_text += f"{body}\n"
                if url:
                    search_text += f"Source: {url}\n"
                search_text += "\n"
            
            logger.info(f"✅ Found {len(results)} results")
            return search_text
            
    except Exception as e:
        logger.error(f"❌ Web search error: {e}")
        return ""
