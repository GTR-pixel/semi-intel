import json, re, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

# Only non-Substack feeds here — Substack blocks all GitHub Actions IPs.
# Substack feeds are fetched directly by the browser in index.html instead.

FEEDS = [
    {"id":"fab-know",      "name":"Fabricated Knowledge", "url":"https://www.fabricatedknowledge.com/feed",  "color":"#2563eb"},
    {"id":"interconnects", "name":"Interconnects",        "url":"https://www.interconnects.ai/feed",         "color":"#16a34a"},
    {"id":"import-ai",     "name":"Import AI",            "url":"https://jack-clark.net/feed/",              "color":"#7c3aed"},
    {"id":"gradient-flow", "name":"Gradient Flow",        "url":"https://gradientflow.com/feed/",            "color":"#7c3aed"},
]

ATOM = "http://www.w3.org/2005/Atom"

def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()

def parse_date(s):
    if not s:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z",
    ]:
        try:
            return datetime.datetime.strptime(s.strip(), fmt).isoformat()
        except:
            pass
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def fetch_rss(feed):
    content = fetch_url(feed["url"])
    root = ET.fromstring(content)
    items = []
    for item in root.findall(".//item")[:15]:
        title = strip_html(item.findtext("title", "")).strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate", "")
        desc = strip_html(item.findtext("description", ""))
        if title:
            items.append({"title":title,"link":link or "#","date":parse_date(pub),
                          "desc":desc[:200],"source":feed["name"],"sourceId":feed["id"],"sourceColor":feed["color"]})
    if not items:
        for entry in root.findall(f".//{{{ATOM}}}entry")[:15]:
            title = strip_html(entry.findtext(f"{{{ATOM}}}title","")).strip()
            link_el = entry.find(f"{{{ATOM}}}link")
            link = link_el.get("href","#") if link_el is not None else "#"
            pub = entry.findtext(f"{{{ATOM}}}published") or entry.findtext(f"{{{ATOM}}}updated") or ""
            desc = strip_html(entry.findtext(f"{{{ATOM}}}summary") or entry.findtext(f"{{{ATOM}}}content") or "")
            if title:
                items.append({"title":title,"link":link,"date":parse_date(pub),
                              "desc":desc[:200],"source":feed["name"],"sourceId":feed["id"],"sourceColor":feed["color"]})
    return items

all_items = []
for feed in FEEDS:
    try:
        items = fetch_rss(feed)
        all_items.extend(items)
        print(f"✓ {feed['name']}: {len(items)} items")
    except Exception as e:
        print(f"✗ {feed['name']}: {e}")

all_items.sort(key=lambda x: x.get("date",""), reverse=True)
output = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(), "items": all_items}
with open("feeds.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\nDone — {len(all_items)} items saved to feeds.json")
