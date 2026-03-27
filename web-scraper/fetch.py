import sys
import urllib.request
import urllib.error
import re

def strip_tags(html):
    # Very basic tag stripping using regex to get plain text
    # Remove script and style elements
    html = re.sub(r'<(script|style).*?</\1>(?is)', '', html)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def fetch_url(url):
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            return strip_tags(html)
    except urllib.error.URLError as e:
        return f"Failed to fetch {url}: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch.py <url>")
        sys.exit(1)

    url_target = sys.argv[1]
    result = fetch_url(url_target)
    print(result)
