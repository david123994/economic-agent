import sqlite3
import datetime
import os
import smtplib
import requests
import json
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from collections import defaultdict

DB_PATH = "news.db"

ECONOMIC_KEYWORDS = [
    "שוק", "מניה", "בורסה", "כלכל", "תקציב", "ריבית", "אינפלציה",
    "בנק", "השקעה", "נדלן", "נדל", "יצוא", "יבוא", "תוצר", "צמיחה",
    "אבטלה", "משכורת", "שכר", "מיסוי", "מס", "תשואה", "קרן",
    "ביטוח", "פנסיה", "אשראי", "הלוואה", "משכנתא", "דירה", "מחיר",
    "יוקר", "עלות", "רווח", "הפסד", "חברה", "סטארטאפ", "היי טק",
    "טכנולוגיה", "ייצוא", "סחר", "דולר", "שקל", "אירו", "מטבע",
    "תשלום", "עסק", "תעשיה", "אנרגיה", "גז", "נפט", "חשמל",
    "קריפטו", "ביטקוין", "נאסדק", "וול סטריט", "תל אביב"
]

BLOCK_KEYWORDS = [
    "מלחמה", "טיל", "רקטה", "חמאס", "חיזבאללה", "עזה", "לבנון",
    "ביטחון", "צבא", "מבצע", "תקיפה", "פצצה", "נשק", "חייל",
    "בחירות", "קואליציה", "אופוזיציה", "כנסת", "ממשלה", "שר ",
    "ספורט", "כדורגל", "כדורסל", "אולימפיאדה", "גביע",
    "סלבריטי", "שחקן", "זמר", "אמן", "סרט", "תוכנית"
]

def is_economic(title):
    has_economic = any(kw in title for kw in ECONOMIC_KEYWORDS)
    has_block = any(kw in title for kw in BLOCK_KEYWORDS)
    return has_economic and not has_block

def get_week_news():
    conn = sqlite3.connect(DB_PATH)
    today = datetime.date.today()
    week_ago = today
    rows = conn.execute(
        "SELECT date,source,title,summary,category,url FROM news WHERE date >= ? ORDER BY date DESC, category",
        (str(week_ago),)
    ).fetchall()
    conn.close()
    filtered = [r for r in rows if is_economic(r[2])]
    print(f"סוננו {len(filtered)} כתבות כלכליות מתוך {len(rows)}")
    return filtered

def gemini_executive_summary(headlines):
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-flash-latest:generateContent?key={api_key}"
     )
    top = headlines[:5]
    prompt = f"""אתה כלכלן בכיר. בהינתן הכותרות הכלכליות הבאות מישראל,
כתוב תקציר מנהלים קצר בעברית של 2 פסקאות בלבד.

כותרות:
{chr(10).join(top)}"""
    body = {"contents": [{"parts": [{"text": prompt}]}]}

    max_retries = 3
    wait_seconds = 20

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=body, timeout=30)
            resp.raise_for_status()
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429 and attempt < max_retries:
                print(f"שגיאת 429 (ניסיון {attempt}/{max_retries}) - ממתין {wait_seconds} שניות...")
                time.sleep(wait_seconds)
                continue
            print(f"שגיאת Gemini: {e}")
            return "לא ניתן היה לייצר תקציר אוטומטי השבוע."
        except Exception as e:
            print(f"שגיאת Gemini: {e}")
            return "לא ניתן היה לייצר תקציר אוטומטי השבוע."

    return "לא ניתן היה לייצר תקציר אוטומטי השבוע."

def build_html(news_rows, exec_summary, week_start, week_end):
    by_cat = defaultdict(list)
    for date, source, title, summary, category, url in news_rows:
        by_cat[category].append({"date": date, "source": source,
                                  "title": title, "summary": summary, "url": url})
    total = sum(len(v) for v in by_cat.values())
    rows_html = ""
    for cat, items in sorted(by_cat.items()):
        rows_html += f"""
        <tr>
          <td colspan="3" style="background:#1e3a5f;color:#fff;padding:10px 16px;
              font-size:15px;font-weight:bold;">{cat} ({len(items)} פריטים)</td>
        </tr>"""
        for i in items:
            link = f'<a href="{i["url"]}" style="color:#1e3a5f;font-size:11px;">קישור</a>' if i["url"] else ""
            rows_html += f"""
        <tr style="border-bottom:1px solid #eee;">
          <td style="padding:10px 16px;font-size:12px;color:#555;width:90px;">
              {i["date"]}<br><span style="color:#999;font-size:11px;">{i["source"]}</span></td>
          <td style="padding:10px 16px;font-size:13px;font-weight:bold;color:#222;">{i["title"]}</td>
          <td style="padding:10px 16px;font-size:12px;color:#444;width:220px;">
              {i["summary"]}<br>{link}</td>
        </tr>"""
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial,sans-serif;direction:rtl;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6f8;padding:20px 0;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0"
  style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
  <tr>
    <td style="background:#1e3a5f;padding:32px 24px;text-align:center;">
      <div style="color:#fff;font-size:24px;font-weight:bold;">דוח כלכלי יומי</div>
      <div style="color:#a8c8f0;font-size:14px;margin-top:6px;">{week_start} - {week_end}</div>
      <div style="color:#cce0f5;font-size:13px;margin-top:4px;">{total} פריטים כלכליים</div>
    </td>
  </tr>
  <tr><td style="padding:24px;">
    <div style="background:#eef4fb;border-right:4px solid #2e6da4;border-radius:6px;padding:16px 20px;">
      <div style="color:#1e3a5f;font-size:14px;font-weight:bold;margin-bottom:10px;">תקציר מנהלים</div>
      <div style="color:#333;font-size:13px;line-height:1.8;">
          {exec_summary.replace(chr(10), "<br>")}</div>
    </div>
  </td></tr>
  <tr><td style="padding:0 24px 24px;">
    <table width="100%" cellpadding="0" cellspacing="0"
      style="border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;">
      <tr style="background:#f8f9fa;">
        <th style="padding:10px 16px;font-size:12px;color:#666;text-align:right;">תאריך</th>
        <th style="padding:10px 16px;font-size:12px;color:#666;text-align:right;">כותרת</th>
        <th style="padding:10px 16px;font-size:12px;color:#666;text-align:right;">סיכום</th>
      </tr>
      {rows_html}
    </table>
  </td></tr>
  <tr><td style="background:#f8f9fa;padding:16px 24px;text-align:center;border-top:1px solid #eee;">
    <div style="color:#999;font-size:11px;">דוח זה נוצר אוטומטית | נשלח כל יום ב-09:00</div>
  </td></tr>
</table></td></tr></table>
</body></html>"""
    return html, total

def send_email(html_body, subject):
    sender = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    recipient = os.environ["EMAIL_RECIPIENT"]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(sender, password)
        s.sendmail(sender, recipient, msg.as_string())
    print(f"הדוח נשלח")

def generate_weekly_report():
    print(f"יצירת דוח שבועי - {datetime.date.today()}")
    today = datetime.date.today()
    week_start = str(today)
    week_end = str(today)
    rows = get_week_news()
    if not rows:
        print("אין חדשות כלכליות השבוע.")
        return
    print(f"נמצאו {len(rows)} פריטים כלכליים")
    headlines = [r[2] for r in rows]
    exec_summary = gemini_executive_summary(headlines)
    html, total = build_html(rows, exec_summary, week_start, week_end)
    subject = f"דוח כלכלי שבועי | {week_start}-{week_end} | {total} פריטים"
    send_email(html, subject)

if __name__ == "__main__":
    generate_weekly_report()

