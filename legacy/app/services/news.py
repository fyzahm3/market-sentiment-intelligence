import httpx
from app.core.cache import cache_get_json, cache_set_json
from app.core.config import settings


async def fetch_news_headlines(ticker: str,limit:int =5):
    cache_key = f"news:{ticker}:{limit}"
    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached

    url = "https://newsapi.org/v2/everything"
    params={
        "q":ticker,
        "apiKey":settings.news_api_key,
        "language":"en",
        "sortBy":"publishedAt",
        "pageSize":limit
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        response=await client.get(url, params=params)
        if response.status_code!=200:
            return []
        data=response.json()
        articles=data.get("articles",[])

        headlines=[article["title"] for article in articles]
        cache_set_json(cache_key, headlines, settings.news_cache_ttl_seconds)
        return headlines
    