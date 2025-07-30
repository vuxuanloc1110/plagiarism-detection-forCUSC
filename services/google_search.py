import aiohttp
import asyncio

from config import SERP_API_KEY
async def async_google_search_serpapi(session, query):
    exact_query = f'"{query}"'  # giữ nguyên tìm chính xác
    search_url = "https://serpapi.com/search"

    params = {
        "engine": "google",
        "q": exact_query,
        "api_key": SERP_API_KEY,
        "num": 5,
    }

    try:
        async with session.get(search_url, params=params, timeout=10) as response:
            if response.status != 200:
                return {"query": query, "result": "Not Found"}
            data = await response.json()

            if "organic_results" not in data or not data["organic_results"]:
                return {"query": query, "result": "Not Found"}

            top_result = data["organic_results"][0]
            return {
                "query": query,
                "title": top_result.get("title", "No title found"),
                "url": top_result.get("link", "No URL found"),
                "snippet": top_result.get("snippet", "No snippet found"),
            }
    except Exception as e:
        return {"query": query, "result": f"Error: {str(e)}"}

async def batch_google_search(queries):
    """Send batch queries to SerpAPI"""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        tasks = [async_google_search_serpapi(session, query) for query in queries]
        return await asyncio.gather(*tasks)