import requests
from bs4 import BeautifulSoup
import sqlite3
import datetime
import time

DB_PATH = "news.db"

RSS_FEEDS = {
    "גלובס": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=585",
    "גלובס שוק ההון": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1111",
    "גלובס נדלן": "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode?iID=1170",
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
        print(f"שגיאה ב-{source_name}: {e}")
    return items

def collect_news():
    print(f"איסוף חדשות - {datetime.date.today()}")
    conn = init_db()
    today = str(datetime.date.today())
    conn.execute("DELETE FROM news WHERE source LIKE '%וואלה%'")
    conn.commit()
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
        try:
            conn.execute(
                "INSERT OR IGNORE INTO news (date,source,title,summary,category,url) VALUES (?,?,?,?,?,?)",
                (today, item["source"], title, "", "כללי", item.get("url", ""))
            )
            conn.commit()
            saved += 1
        except Exception as e:
            print(f"שגיאת DB: {e}")
    print(f"נשמרו {saved} כתבות.")
    conn.close()

if __name__ == "__main__":
    collect_news()

