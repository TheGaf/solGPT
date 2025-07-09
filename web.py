import os
import requests
import logging

def brave_search(query):
    headers = {"Accept": "application/json", "X-Subscription-Token": os.getenv("BRAVE_API_KEY")}
    params = {"q": query[:200], "count": 5, "freshness": "day"}
    try:
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers=headers,
            params=params,
            timeout=5
        )
        resp.raise_for_status()
        items = resp.json().get("web", {}).get("results", []) or []
        return [{"title": i.get("title"), "url": i.get("url"), "description": i.get("description")} for i in items]
    except Exception as e:
        logging.error(f"Brave search failed: {e}")
        return []

def format_brave_html(results):
    html = []
    for idx, r in enumerate(results, start=1):
        html.append(
            f"<p><strong>[{idx}] <a href='{r['url']}' target='_blank' rel='noopener'>{r['title']}</a></strong><br>{r['description']}</p>"
        )
    return "".join(html)
