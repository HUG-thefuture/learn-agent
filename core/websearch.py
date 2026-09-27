# -*- coding: utf-8 -*-
"""网络数据检索：DuckDuckGo / Bing 双通道 + 网页正文抽取。"""
import re

import requests

from core.config import cfg

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

_TAG = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return _TAG.sub("", html).replace("&quot;", '"').replace("&#39;", "'") \
               .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").strip()


def search(query: str, limit: int = 5) -> list:
    """返回 [{title,url,snippet}]；两个引擎任选可用的。"""
    if not cfg().get("web", {}).get("search_enabled", True):
        return []
    results = []
    try:
        results = _ddg(query, limit)
    except Exception:
        pass
    if not results:
        try:
            results = _bing(query, limit)
        except Exception:
            pass
    return results[:limit]


def _ddg(query, limit):
    r = requests.post("https://html.duckduckgo.com/html/",
                      data={"q": query}, headers={"User-Agent": _UA},
                      timeout=cfg()["web"]["timeout"])
    r.raise_for_status()
    out = []
    for m in re.finditer(
            r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'class="result__snippet"[^>]*>(.*?)</a>',
            r.text, re.S):
        url, title, snip = m.group(1), _clean(m.group(2)), _clean(m.group(3))
        if url.startswith("//duckduckgo.com/l/?uddg="):
            import urllib.parse as up
            q = up.parse_qs(up.urlparse("https:" + url).query)
            url = q.get("uddg", [url])[0]
        out.append({"title": title, "url": url, "snippet": snip[:300]})
        if len(out) >= limit:
            break
    return out


def _bing(query, limit):
    r = requests.get("https://www.bing.com/search",
                     params={"q": query, "setlang": "zh-hans", "count": limit},
                     headers={"User-Agent": _UA},
                     timeout=cfg()["web"]["timeout"])
    r.raise_for_status()
    out = []
    for m in re.finditer(r'<li class="b_algo".*?<h2><a[^>]+href="([^"]+)"[^>]*>(.*?)</a></h2>.*?<p[^>]*>(.*?)</p>',
                         r.text, re.S):
        out.append({"url": m.group(1), "title": _clean(m.group(2)),
                    "snippet": _clean(m.group(3))[:300]})
        if len(out) >= limit:
            break
    return out


def fetch_text(url: str, max_chars: int = None) -> str:
    """抓取网页并抽取正文文本。"""
    cfg_web = cfg()["web"]
    max_chars = max_chars or cfg_web.get("max_chars", 6000)
    r = requests.get(url, headers={"User-Agent": _UA}, timeout=cfg_web["timeout"])
    r.raise_for_status()
    html = r.text
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = _TAG.sub(" ", html)
    text = re.sub(r"\s+", " ", text)
    return text[:max_chars]
