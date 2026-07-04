import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import os
import json
import time

DB_PATH = "news.db"

RSS_FEEDS = {
    "גלובס": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585",
    "גלובס שוק ההון": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1111",
    "גלובס נדלן": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1170",
    "ינט כלכלה": "https://www.ynet.co.il/Integration/StoryRss3370.xml",
    "וואלה כלכלה": "https://rss.walla.co.il/feed/9",
    "ביזפורטל": "https://www.bizportal.co.il/rss/rss.xml",
}
HEADERS = {"User-Agent": "Mozilla/5.0 Chrome/120.0"}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, source TEXT, title TEXT,
            summary TEXT, category TEXT, url TEXT,
            UNIQUE(date, title)
        )
    """)
    conn.commit()
    return conn


def fetch_rss(source_name, rss_url):
    items = []
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.content, "xml")
        for item in soup.find_all("item")[:15]:
            title = item.find("title")
            link = item.find("link")
            if title and len(title.get_text(strip=True)) > 10:
                items.append({
                    "source": source_name,
                    "title": title.get_text(strip=True),
                    "url": link.get_text(strip=True) if link else "",
                })
    except Exception as e:
        print(f"  שגיאה ב-{source_name}: {e}")
    return items


def gemini_summarize(title):
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={api_key}"
    )
    prompt = f"""אתה עוזר לניתוח חדשות כלכליות בישראל.
בהינתן הכותרת הבאה, החזר JSON בלבד עם השדות:
- summary: סיכום קצר של 1-2 משפטים בעברית
- category: אחת מהקטגוריות: מאקרו | שוק ההון | נדל"ן | טכנולוגיה | בנקאות | אנרגיה | סחר חוץ | כללי

כותרת: {title}"""
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, json=body, timeout=20)
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        return data.get("summary", ""), data.get("category", "כללי")
    except Exception as e:
        print(f"  שגיאת Gemini: {e}")
        return "", "כללי"


def collect_news():
    print(f"\n📰 איסוף חדשות — {datetime.date.today()}")
    conn = init_db()
    today = str(datetime.date.today())
    saved = 0
    all_items = []
    for name, url in RSS_FEEDS.items():
        items = fetch_rss(name, url)
        print(f"  {name}: {len(items)} פריטים")
        all_items.extend(items)
    seen = set()
    for item in all_items:
        title = item["title"]
        if title in seen:
            continue
        seen.add(title)
        print(f"  ✍️  מסכם: {title[:55]}...")
        summary, category = gemini_summarize(title)
        time.sleep(3)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO news (date,source,title,summary,category,url) VALUES (?,?,?,?,?,?)",
                (today, item["source"], title, summary, category, item.get("url", ""))
            )
            conn.commit()
            saved += 1
        except Exception as e:
            print(f"  שגיאת DB: {e}")
    print(f"\n✅ נשמרו {saved} כתבות.")
    conn.close()


if __name__ == "__main__":
    collect_news()
