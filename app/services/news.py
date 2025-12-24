import httpx
from app.core.config import settings
async def fetch_news_headlines(ticker: str,limit:int =5):
    url = "https://newsapi.org/v2/everything"
    params={
        "q":ticker,
        "apikey":settings.news_api_key,
        "language":"en",
        "sortBy":"publishedAt",
        "pageSize":limit
    }

    async with httpx.AsyncClient() as client:
        response=await client.get(url, params=params)
        if response.status_code!=200:
            print(f"Error fetching news: {response.text}")
            return []
        data=response.json()
        articles=data.get("articles",[])

        headlines=[article["title"] for article in articles]

        return headlines
    