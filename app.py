import os
import json
import asyncio
from typing import List, Dict
from collections import Counter
from datetime import datetime

from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from dotenv import load_dotenv
import httpx
from openai import OpenAI
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import numpy as np

# ------------------------------
# Load ENV
# ------------------------------
load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not NEWS_API_KEY or not GROQ_API_KEY:
    raise RuntimeError("Missing API keys")

# ------------------------------
# Gemini Client
# ------------------------------
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)

GORK_MODELS = [
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "llama-3.1-8b-instant",
]

# ------------------------------
# FastAPI App
# ------------------------------
app = FastAPI(title="TruthLens Intelligence Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Static Files
# ------------------------------
app.mount("/static", StaticFiles(directory="static"), name="static-files")
app.mount("/templates", StaticFiles(directory="templates"), name="templates")  # html files

# ------------------------------
# Gemini Fallback Engine
# ------------------------------
async def query_gork(prompt: str):
    for model_name in GORK_MODELS:
        try:
            response = client.responses.create(
                model=model_name,
                input=prompt
            )

            if response.output_text:
                return response.output_text.strip()

        except Exception:
            continue

    return None

# ------------------------------
# Sentiment Analysis
# ------------------------------
async def analyze_sentiment(text: str):
    prompt = f"""
Classify sentiment of this news text.
Return ONLY JSON:

{{
  "label": "positive | neutral | negative",
  "score": 0 to 1
}}

Text:
{text}
"""
    response = await query_gork(prompt)
    try:
        clean = response.replace("```json", "").replace("```", "")
        return json.loads(clean)
    except:
        return {"label": "neutral", "score": 0.5}

# ------------------------------
# Fake News Detection
# ------------------------------
async def detect_fake_news(text: str):
    prompt = f"""
Analyze this news article for misinformation risk.

Return ONLY JSON:

{{
  "fake_probability": 0 to 1,
  "reason": "short explanation"
}}

Article:
{text}
"""
    response = await query_gork(prompt)
    try:
        clean = response.replace("```json", "").replace("```", "")
        return json.loads(clean)
    except:
        return {"fake_probability": 0.2, "reason": "Insufficient data"}

# ------------------------------
# Summarization
# ------------------------------
async def summarize(text: str):
    prompt = f"""
Summarize this article in 3 concise neutral sentences:

{text}
"""
    response = await query_gork(prompt)
    return response or "Summary unavailable."

# ------------------------------
# News Fetching
# ------------------------------
async def fetch_news(country="", category="", q=""):

    url = "https://newsapi.org/v2/everything" if q else "https://newsapi.org/v2/top-headlines"

    params = {
        "apiKey": NEWS_API_KEY,
        "pageSize": 10
    }

    if q:
        params["q"] = q
        params["language"] = "en"
        params["sortBy"] = "publishedAt"
    else:
        if country:
            params["country"] = country
        if category:
            params["category"] = category

    async with httpx.AsyncClient(timeout=15) as client_http:
        response = await client_http.get(url, params=params)

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="News API error")

    articles = response.json().get("articles", [])

    tasks = []
    for article in articles:
        content = article.get("description") or article.get("content") or ""
        tasks.append(process_article(article, content))

    results = await asyncio.gather(*tasks)
    return results


async def process_article(article, content):
    summary, sentiment, fake = await asyncio.gather(
        summarize(content),
        analyze_sentiment(content),
        detect_fake_news(content)
    )

    return {
        "title": article.get("title"),
        "summary": summary,
        "url": article.get("url"),
        "source": article.get("source", {}).get("name"),
        "sentiment": sentiment,
        "fake_probability": fake.get("fake_probability"),
        "fake_reason": fake.get("reason")
    }

# ------------------------------
# Trend Detection
# ------------------------------
def detect_trends(articles):
    words = []
    for a in articles:
        words += a["title"].lower().split()
    common = Counter(words).most_common(5)
    trending = [word for word, count in common if len(word) > 4]
    return trending

# ------------------------------
# Topic Clustering
# ------------------------------
def cluster_topics(articles):

    texts = [a.get("summary", "") for a in articles if a.get("summary")]

    if len(texts) < 3:
        return articles

    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(texts)

    kmeans = KMeans(n_clusters=3, random_state=42)
    clusters = kmeans.fit_predict(X)

    for i, cluster_id in enumerate(clusters):
        if i < len(articles):
            articles[i]["topic_cluster"] = int(cluster_id)

    return articles

# ------------------------------
# Routes
# ------------------------------
@app.get("/api/top-news")
async def get_top_news(
    country: str = Query(default=""),
    category: str = Query(default=""),
    q: str = Query(default="")
):
    try:
        articles = await fetch_news(country, category, q)
        articles = cluster_topics(articles)
        trends = detect_trends(articles)
        return {"articles": articles, "trending_keywords": trends, "timestamp": datetime.utcnow()}
    except Exception:
        return {"articles": []}

@app.get("/api/check-news")
async def check_news(title: str):
    prompt = f"""
Search the web for perspectives on:

"{title}"

Return STRICT JSON:

{{
  "bias": {{
    "left": [{{"title": "...", "url": "...", "bias_score": 0-40}}],
    "center": [{{"title": "...", "url": "...", "bias_score": 45-55}}],
    "right": [{{"title": "...", "url": "...", "bias_score": 60-100}}]
  }}
}}

Only JSON.
"""
    response = await query_gork(prompt)
    try:
        clean = response.replace("```json", "").replace("```", "")
        return json.loads(clean)
    except:
        return {"bias": {"left": [], "center": [], "right": []}}

# Serve frontend HTML
@app.get("/")
async def serve_home():
    return FileResponse("templates/index.html")

# ------------------------------
# Run
# ------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)