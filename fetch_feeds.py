import json, re, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

# Feed types:
# "rss"      — fetch standard RSS/Atom directly (works for non-Substack domains)
# "substack" — use Substack's own JSON API (avoids 403 on RSS endpoint from GitHub IPs)

FEEDS = [
    # Direct RSS — non-Substack domains, work fine
    {"id":"fab-know",      "name":"Fabricated Knowledge", "type":"rss",      "url":"https://www.fabricatedknowledge.com/feed",  "color":"#2563eb"},
    {"id":"interconnects", "name":"Interconnects",        "type":"rss",      "url":"https://www.interconnects.ai/feed",         "color":"#16a34a"},
    {"id":"import-ai",     "name":"Import AI",            "type":"rss",      "url":"https://jack-clark.net/feed/",              "color":"#7c3aed"},
    {"id":"gradient-flow", "name":"Gradient Flow",        "type":"rss",      "url":"https://gradientflow.com/feed/",            "color":"#7c3aed"},

    # Substack JSON API — bypasses RSS 403 block on GitHub Actions IPs
    {"id":"chip-letter",   "name":"The Chip Letter",      "type":"substack", "substack":"thechipletter",    "color":"#2563eb"},
    {"id":"moore",         "name":"More Than Moore",      "type":"substack", "substack":"morethanmoore",    "color":"#2563eb"},
    {"id":"chinatalk",     "name":"ChinaTalk",            "type":"substack", "substack":"chinatalk",        "color":"#16a34a"},
    {"id":"state-ai",      "name":"State of AI",          "type":"substack", "substack":"nathanbenaich",    "color":"#7c3aed"},
    {"id":"doroshenko",    "name":"D. Doroshenko",        "type":"substack", "substack":"denisdoroshenko",  "color":"#d97706"},
    {"id":"asianometry",   "name":"Asianometry",          "type":"substack", "substack":"asianometry",      "color":"#64748b"},
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
        "%Y-%m-%dT%H:%M:%S",
    ]:
        try:
            return datetime.datetime.strptime(s.strip(), fmt).isoformat()
        except:
            pass
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def fetch_url(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/atom+xml, application/json, application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
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
        desc = strip_html(item.findtext("description", "") or "")
        if title:
            items.append(make_item(title, link or "#", parse_date(pub), desc, feed))

    if not items:
        for entry in root.findall(f".//{{{ATOM}}}entry")[:15]:
            title = strip_html(entry.findtext(f"{{{ATOM}}}title", "")).strip()
            link_el = entry.find(f"{{{ATOM}}}link")
            link = link_el.get("href", "#") if link_el is not None else "#"
            pub = entry.findtext(f"{{{ATOM}}}published") or entry.findtext(f"{{{ATOM}}}updated") or ""
            desc = strip_html(entry.findtext(f"{{{ATOM}}}summary") or entry.findtext(f"{{{ATOM}}}content") or "")
            if title:
                items.append(make_item(title, link, parse_date(pub), desc, feed))

    return items

def fetch_substack(feed):
    # Substack's JSON API — different endpoint, not blocked like /feed
    url = f"https://{feed['substack']}.substack.com/api/v1/posts?limit=15"
    content = fetch_url(url)
    posts = json.loads(content)
    items = []
    for post in posts:
        title = (post.get("title") or "").strip()
        link = post.get("canonical_url") or f"https://{feed['substack']}.substack.com"
        pub = post.get("post_date") or post.get("publishedAt") or ""
        desc = strip_html(post.get("subtitle") or post.get("description") or "")
        if title:
            items.append(make_item(title, link, parse_date(pub), desc, feed))
    return items

def make_item(title, link, date, desc, feed):
    return {
        "title": title,
        "link": link,
        "date": date,
        "desc": desc[:200],
        "source": feed["name"],
        "sourceId": feed["id"],
        "sourceColor": feed["color"],
    }

def fetch_hn():
    queries = ["semiconductor", "TSMC", "HBM memory", "AI chip", "GPU compute", "foundry"]
    seen = set()
    items = []
    for q in queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}&tags=story&hitsPerPage=8"
            content = fetch_url(url, timeout=10)
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
        if feed["type"] == "substack":
            items = fetch_substack(feed)
        else:
            items = fetch_rss(feed)
        all_items.extend(items)
        print(f"✓ {feed['name']}: {len(items)} items")
    except Exception as e:
        print(f"✗ {feed['name']}: {e}")

print("Fetching Hacker News...")
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
