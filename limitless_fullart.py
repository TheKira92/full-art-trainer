#!/usr/bin/env python3
"""
limitless_fullart.py
--------------------
Enumera le carte con art speciale (Full Art / Alternate Art e simili) dal
Card Database di Limitless usando la ricerca avanzata.
Sintassi: https://limitlesstcg.com/cards/syntax

Estrae, per ogni carta: set, numero, lingua, URL della pagina e URL immagine.
NON visita le singole pagine -> una sola richiesta, molto veloce.

Di default usa il criterio per RARITA (r>r = rarita superiore a Rare):
per i Trainer questo cattura tutte le full art / alt art di ogni epoca,
comprese le promo giapponesi vecchie (Sun & Moon e precedenti) che non
hanno l'etichetta is:fa/aa. Database inglese + giapponese (lang:en,jp).

Con --match art torna al criterio per etichetta (is:fa,aa), piu preciso
ma incompleto sui set giapponesi vecchi.

Dipendenze:
  pip install requests beautifulsoup4

Esempi:
  # Trainer con art speciale, EN + JP, tutte le epoche (default)
  python limitless_fullart.py --type trainer

  # Solo etichette Full Art / Alt Art (criterio vecchio)
  python limitless_fullart.py --type trainer --match art --appearance fa,aa

  # Solo inglese
  python limitless_fullart.py --type trainer --lang en

  # Query personalizzata (qualsiasi sintassi Limitless)
  python limitless_fullart.py --query "r>r -t:pkmn -t:energy lang:jp e:SM12a"
"""

import argparse
import csv
import json
import re
import sys
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SEARCH_URL = "https://limitlesstcg.com/cards"
SITE = "https://limitlesstcg.com"

# Mappa comoda --type -> frammento di query Limitless
TYPE_QUERY = {
    "pkmn": "t:pkmn",
    "trainer": "-t:pkmn -t:energy",  # tutto cio che non e Pokemon ne Energia = Trainer
    "supporter": "t:su",
    "item": "t:item",
    "stadium": "t:st",
    "tool": "t:tool",
    "energy": "t:energy",
    "all": "",                  # nessun filtro di tipo
}

# Pattern del link a una singola carta: /cards/{LINGUA}/{SET}/{NUMERO}
# (la lingua e' opzionale, per robustezza verso eventuali varianti)
CARD_HREF_RE = re.compile(r"^/cards/(?:([a-z][a-z.]*)/)?([A-Za-z0-9]+)/([A-Za-z0-9]+)$")


def build_query(args):
    if args.query:
        # query manuale: rispettala cosi com'e, aggiungi solo show:all se assente
        q = args.query
        if "show:" not in q:
            q += " show:all"
        return q
    if args.match == "rare":
        # rarita superiore a "rare": per i Trainer = tutte le full/alt art,
        # comprese le giapponesi vecchie non etichettate is:fa/aa
        parts = [f"r>{args.rarity_min}"]
    else:
        parts = [f"is:{args.appearance}"]
    tq = TYPE_QUERY.get(args.type, TYPE_QUERY["trainer"])
    if tq:
        parts.append(tq)
    q = " ".join(parts)
    # opzioni di ricerca dentro la query stessa
    q += f" lang:{args.lang} show:all"
    return q


def to_large_image(url):
    """Deriva la versione LG (grande) dall'URL immagine SM, se possibile."""
    if not url:
        return ""
    return re.sub(r"_SM(\.\w+)$", r"_LG\1", url)


def main():
    ap = argparse.ArgumentParser(description="Carte Full Art dal database Limitless")
    ap.add_argument("--type", choices=list(TYPE_QUERY.keys()), default="trainer",
                    help="categoria di carte (default: trainer)")
    ap.add_argument("--match", choices=["rare", "art"], default="rare",
                    help="criterio: 'rare' = rarita > Rare (cattura full/alt art di "
                         "tutte le epoche, anche JP vecchie); 'art' = etichette "
                         "is:fa/aa (preciso ma incompleto sui set JP vecchi). Default: rare")
    ap.add_argument("--rarity-min", default="r",
                    help="con --match rare: soglia di rarita esclusa (default: r = Rare, "
                         "quindi prende tutto cio che e' sopra Rare)")
    ap.add_argument("--appearance", default="fa,aa",
                    help="con --match art: versioni art fa,aa,rainbow,gold,shiny "
                         "separate da virgola (default: fa,aa)")
    ap.add_argument("--lang", default="en,jp",
                    help="lingue separate da virgola: en, jp, de, fr, es, it, pt "
                         "(default: en,jp)")
    ap.add_argument("--query", default=None,
                    help="query Limitless completa, sovrascrive --type/--lang/--appearance")
    ap.add_argument("--out-prefix", default="fullart")
    args = ap.parse_args()

    query = build_query(args)
    session = requests.Session()
    session.headers.update({"User-Agent": "limitless-fullart/1.0"})

    print(f"Query: {query}", file=sys.stderr)
    resp = session.get(SEARCH_URL, params={"q": query}, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Quante carte dichiara la pagina? ("722 cards found where ...")
    declared = None
    m = re.search(r"([\d,]+)\s+cards?\s+found", soup.get_text(" ", strip=True))
    if m:
        declared = int(m.group(1).replace(",", ""))

    # Raccoglie ogni link carta univoco (set, numero) + immagine.
    seen = set()
    rows = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # normalizza href assoluto -> path
        path = urlparse(href).path if href.startswith("http") else href
        cm = CARD_HREF_RE.match(path)
        if not cm:
            continue
        lang, card_set, number = cm.group(1) or "", cm.group(2), cm.group(3)
        key = (lang, card_set, number)
        if key in seen:
            continue
        seen.add(key)
        img = a.find("img")
        img_url = ""
        if img:
            img_url = img.get("src") or img.get("data-src") or ""
        rows.append({
            "set": card_set,
            "numero": number,
            "lingua": lang,
            "url_carta": f"{SITE}{path}",
            "url_immagine": img_url,
            "url_immagine_grande": to_large_image(img_url),
        })

    if not rows:
        if declared == 0 or declared is None:
            print(f"La ricerca non ha prodotto risultati (la pagina dichiara: "
                  f"{declared} carte). Controlla la query: {query}", file=sys.stderr)
        else:
            print(f"ATTENZIONE: la pagina dichiara {declared} carte ma non ne ho "
                  f"estratta nessuna -> probabile problema di parsing dei link. "
                  f"Segnalamelo.", file=sys.stderr)
        sys.exit(1)

    # Output
    with open(f"{args.out_prefix}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(f"{args.out_prefix}.json", "w", encoding="utf-8") as f:
        json.dump({"query": query, "trovate": len(rows), "dichiarate": declared,
                   "cards": rows}, f, ensure_ascii=False, indent=2)

    print(f"\nCarte estratte: {len(rows)}")
    if declared is not None:
        print(f"Carte dichiarate dalla pagina: {declared}")
        if declared != len(rows):
            print("  ATTENZIONE: i due numeri non coincidono. La pagina potrebbe "
                  "essere paginata diversamente; segnalamelo.", file=sys.stderr)
    # ripartizione per lingua (per verificare che il giapponese sia incluso)
    from collections import Counter
    bylang = Counter(r["lingua"] or "?" for r in rows)
    print("Per lingua:", ", ".join(f"{k}={v}" for k, v in bylang.most_common()))
    print(f"\nPrime 15:")
    for r in rows[:15]:
        print(f"  {r['lingua'] or '?':3s} {r['set']:6s} #{r['numero']:>4}  {r['url_carta']}")
    print(f"\nSalvati: {args.out_prefix}.csv e {args.out_prefix}.json", file=sys.stderr)


if __name__ == "__main__":
    main()