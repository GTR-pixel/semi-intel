import json, re, datetime, urllib.request, urllib.parse, urllib.error
import xml.etree.ElementTree as ET

FEEDS = [
    {"id":"chip-letter",   "name":"The Chip Letter",     "url":"https://thechipletter.substack.com/feed",    "color":"#2563eb"},
    {"id":"fab-know",      "name":"Fabricated Knowledge", "url":"https://www.fabricatedknowledge.com/feed",   "color":"#2563eb"},
    {"id":"moore",         "name":"More Than Moore",      "url":"https://morethanmoore.substack.com/feed",    "color":"#2563eb"},
    {"id":"chinatalk",     "name":"ChinaTalk",            "url":"https://www.chinatalk.media/rss",            "color":"#16a34a"},
    {"id":"interconnects", "name":"Interconnects",        "url":"https://www.interconnects.ai/feed",          "color":"#16a34a"},
    {"id":"state-ai",      "name":"State of AI",          "url":"https://nathanbenaich.substack.com/feed",    "color":"#7c3aed"},
    {"id":"import-ai",     "name":"Import AI",            "url":"https://jack-clark.net/feed/",               "color":"#7c3aed"},
    {"id":"gradient-flow", "name":"Gradient Flow",        "url":"https://gradientflow.com/feed/",             "color":"#7c3aed"},
    {"id":"doroshenko",    "name":"D. Doroshenko",        "url":"https://denisdoroshenko.substack.com/feed",  "color":"#d97706"},
    {"id":"asianometry",   "name":"Asianometry",          "url":"https://asianometry.substack.com/feed",      "color":"#64748b"},
]

ATOM = "http://www.w3.org/2005/Atom"

def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()

def parse_date(s):
    if not s:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ]:
        try:
            return datetime.datetime.strptime(s.strip(), fmt).isoformat()
        except:
            pass
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def fetch_url(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; SemiIntel/1.0; +https://github.com)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    })
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", errors="replace")

def parse_feed(content, feed):
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"XML parse error: {e}")

    # Try RSS
    for item in root.findall(".//item")[:15]:
        title = strip_html(item.findtext("title", "")).strip()
        link = (item.findtext("link") or "").strip()
        pub = item.findtext("pubDate", "") or item.findtext("dc:date", "")
        desc = strip_html(item.findtext("description", "") or item.findtext("content:encoded", ""))
        if title:
            items.append({
                "title": title, "link": link or "#",
                "date": parse_date(pub), "desc": desc[:200],
                "source": feed["name"], "sourceId": feed["id"], "sourceColor": feed["color"],
            })

    # Try Atom
    if not items:
        for entry in root.findall(f".//{{{ATOM}}}entry")[:15]:
            title = strip_html(entry.findtext(f"{{{ATOM}}}title", "")).strip()
            link_el = entry.find(f"{{{ATOM}}}link")
            link = (link_el.get("href", "#") if link_el is not None else "#")
            pub = (entry.findtext(f"{{{ATOM}}}published") or
                   entry.findtext(f"{{{ATOM}}}updated") or "")
            desc = strip_html(
                entry.findtext(f"{{{ATOM}}}summary") or
                entry.findtext(f"{{{ATOM}}}content") or ""
            )
            if title:
                items.append({
                    "title": title, "link": link,
                    "date": parse_date(pub), "desc": desc[:200],
                    "source": feed["name"], "sourceId": feed["id"], "sourceColor": feed["color"],
                })

    return items

def fetch_hn():
    queries = ["semiconductor", "TSMC", "HBM memory", "AI chip", "GPU compute"]
    seen = set()
    items = []
    for q in queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}&tags=story&hitsPerPage=8"
            content = fetch_url(url)
            data = json.loads(content)
            for h in data.get("hits", []):
                if h["objectID"] not in seen and h.get("title"):
                    seen.add(h["objectID"])
                    items.append({
                        "title": h["title"],
                        "link": h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                        "date": h.get("created_at", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                        "desc": "",
                        "source": "Hacker News",
                        "sourceId": "hn",
                        "sourceColor": "#d97706",
                    })
        except Exception as e:
            print(f"  HN query '{q}' failed: {e}")
    return items

# ── Main ────────────────────────────────────────────────────────

all_items = []

for feed in FEEDS:
    try:
        content = fetch_url(feed["url"])
        items = parse_feed(content, feed)
        all_items.extend(items)
        print(f"✓ {feed['name']}: {len(items)} items")
    except Exception as e:
        print(f"✗ {feed['name']}: {e}")

print("Fetching Hacker News…")
try:
    hn = fetch_hn()
    all_items.extend(hn)
    print(f"✓ Hacker News: {len(hn)} items")
except Exception as e:
    print(f"✗ Hacker News: {e}")

all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

output = {
    "updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "items": all_items,
}

with open("feeds.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\nDone — {len(all_items)} total items saved to feeds.json")
