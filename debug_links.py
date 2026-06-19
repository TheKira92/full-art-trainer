#!/usr/bin/env python3
"""Diagnostica: mostra il formato reale dei link/immagini nella pagina di ricerca."""
import requests
from bs4 import BeautifulSoup

r = requests.get(
    "https://limitlesstcg.com/cards",
    params={"q": "is:fa -t:pkmn -t:energy lang:en show:all"},
    headers={"User-Agent": "debug/1.0"},
    timeout=60,
)
print("HTTP status:", r.status_code, "| lunghezza HTML:", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")

hrefs = [a["href"] for a in soup.find_all("a", href=True) if "cards" in a["href"].lower()]
print("\nLink che contengono 'cards':", len(hrefs))
for h in hrefs[:25]:
    print("   href ->", repr(h))

imgs = [(i.get("src"), i.get("data-src")) for i in soup.find_all("img")]
print("\nImmagini totali:", len(imgs))
for src, dsrc in imgs[:12]:
    print("   img  -> src=", repr(src), " data-src=", repr(dsrc))