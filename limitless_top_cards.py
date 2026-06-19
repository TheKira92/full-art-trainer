#!/usr/bin/env python3
"""
limitless_top_cards.py
----------------------
Aggrega le carte piu giocate nei tornei Pokemon TCG da Limitless (API
ufficiale, nessuna chiave) e, opzionalmente, arricchisce ogni carta con
la RARITA letta dal Card Database (limitlesstcg.com/cards/{SET}/{NUM}).

Doc API: https://docs.limitlesstcg.com/developer/tournaments

Dipendenze:
  pip install requests beautifulsoup4

Esempi:
  # senza rarita (veloce)
  python limitless_top_cards.py --tournaments 40 --min-players 16 --top 60

  # con rarita (piu lento: una richiesta per carta unica, ma con cache)
  python limitless_top_cards.py --tournaments 40 --min-players 16 --rarity

  # solo Pokemon giocati in almeno il 5% dei deck
  python limitless_top_cards.py --rarity --categoria pokemon --min-inclusione 5
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict

import requests
from bs4 import BeautifulSoup

API_BASE = "https://play.limitlesstcg.com/api"
CARD_BASE = "https://limitlesstcg.com/cards"
KNOWN_SECTIONS = ["pokemon", "trainer", "trainers", "energy", "energies"]

# Rarita note, ordinate dalla piu lunga alla piu corta per un match corretto.
RARITIES = [
    "Special Illustration Rare", "Illustration Rare", "Special Art Rare",
    "Character Super Rare", "Character Holo Rare", "Rainbow Rare",
    "Radiant Rare", "Amazing Rare", "Triple Rare", "Double Rare",
    "Secret Rare", "Ultra Rare", "Hyper Rare", "Shiny Rare", "Holo Rare",
    "Art Rare", "Promo", "Uncommon", "Common", "Rare",
]
RARITY_RE = re.compile(r"(" + "|".join(re.escape(r) for r in RARITIES) + r")")

CACHE_FILE = "rarity_cache.json"


def get_json(session, url, params=None, max_retries=5):
    for attempt in range(max_retries):
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 2 ** attempt))
            print(f"  rate limit, attendo {wait}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"Troppi retry per {url}")


def list_tournaments(session, game, fmt, limit):
    tournaments, page = [], 1
    while len(tournaments) < limit:
        params = {"game": game, "limit": min(50, limit - len(tournaments)), "page": page}
        if fmt:
            params["format"] = fmt
        batch = get_json(session, f"{API_BASE}/tournaments", params=params)
        if not batch:
            break
        tournaments.extend(batch)
        if len(batch) < params["limit"]:
            break
        page += 1
    return tournaments[:limit]


def extract_cards(decklist):
    """Ritorna lista di (chiave, nome, copie, categoria, set, numero)."""
    cards = []
    if not decklist or not isinstance(decklist, dict):
        return cards
    sections = [k for k in decklist if isinstance(decklist[k], list)]
    if not sections:
        sections = [k for k in KNOWN_SECTIONS if k in decklist]
    for section in sections:
        for entry in decklist[section]:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name") or entry.get("card") or "?"
            count = entry.get("count") or entry.get("number_of_copies") or entry.get("amount") or 0
            card_set = entry.get("set") or ""
            number = entry.get("number") or entry.get("cardNumber") or ""
            try:
                count = int(count)
            except (ValueError, TypeError):
                count = 0
            if count <= 0:
                continue
            key = f"{name} ({card_set}-{number})" if (card_set and number) else name
            cards.append((key, name, count, section, card_set, str(number)))
    return cards


def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def fetch_rarity(session, card_set, number, cache, delay):
    """Legge la rarita dalla pagina della carta nel database Limitless."""
    if not card_set or not number:
        return ""
    ck = f"{card_set}-{number}"
    if ck in cache:
        return cache[ck]
    url = f"{CARD_BASE}/{card_set}/{number}"
    rarity = ""
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Il set/rarita stanno in un link verso /cards/{SET}: cerchiamo li,
            # con fallback sul testo completo della pagina.
            text = ""
            for a in soup.find_all("a", href=True):
                if a["href"].rstrip("/").endswith(f"/cards/{card_set}"):
                    text = a.get_text(" ", strip=True)
                    if "#" in text:
                        break
            if not text:
                text = soup.get_text(" ", strip=True)
            m = re.search(r"#\s*" + re.escape(str(number)) + r"[^A-Za-z]{0,8}" + RARITY_RE.pattern, text)
            if m:
                rarity = m.group(1)
            else:
                m2 = RARITY_RE.search(text)
                rarity = m2.group(1) if m2 else ""
    except Exception as e:
        print(f"    rarita fallita {ck}: {e}", file=sys.stderr)
    cache[ck] = rarity
    time.sleep(delay)
    return rarity


def main():
    ap = argparse.ArgumentParser(description="Carte piu giocate dai tornei Limitless")
    ap.add_argument("--game", default="PTCG")
    ap.add_argument("--format", default="STANDARD")
    ap.add_argument("--tournaments", type=int, default=40)
    ap.add_argument("--min-players", type=int, default=8)
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--delay", type=float, default=0.4, help="pausa tra richieste API tornei")
    ap.add_argument("--card-delay", type=float, default=0.25, help="pausa tra richieste pagine carta")
    ap.add_argument("--rarity", action="store_true", help="arricchisci con la rarita (piu lento)")
    ap.add_argument("--categoria", choices=["pokemon", "trainer", "energy"], default=None,
                    help="mostra solo una categoria")
    ap.add_argument("--min-inclusione", type=float, default=0.0,
                    help="scarta le carte sotto questa %% di inclusione")
    ap.add_argument("--out-prefix", default="top_cards")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": "limitless-top-cards/1.1"})

    print(f"Recupero fino a {args.tournaments} tornei {args.game}/{args.format}...", file=sys.stderr)
    tournaments = list_tournaments(session, args.game, args.format, args.tournaments)
    print(f"Trovati {len(tournaments)} tornei.", file=sys.stderr)

    total_copies = defaultdict(int)
    deck_count = defaultdict(int)
    display_name, section_of, setnum_of = {}, {}, {}
    decks_analyzed = 0

    for t in tournaments:
        if t.get("players", 0) < args.min_players:
            continue
        tid = t["id"]
        try:
            standings = get_json(session, f"{API_BASE}/tournaments/{tid}/standings")
        except Exception as e:
            print(f"  salto {tid}: {e}", file=sys.stderr)
            continue
        time.sleep(args.delay)
        for player in standings:
            cards = extract_cards(player.get("decklist"))
            if not cards:
                continue
            decks_analyzed += 1
            seen = set()
            for key, name, count, section, cset, cnum in cards:
                total_copies[key] += count
                display_name[key] = name
                section_of[key] = section
                setnum_of[key] = (cset, cnum)
                if key not in seen:
                    deck_count[key] += 1
                    seen.add(key)
        print(f"  {t.get('name','?')[:50]:50s} ({t.get('players','?')} giocatori) -> deck finora: {decks_analyzed}", file=sys.stderr)

    if decks_analyzed == 0:
        print("Nessuna decklist trovata. Aumenta --tournaments o abbassa --min-players.", file=sys.stderr)
        sys.exit(1)

    # Normalizza i nomi delle categorie
    def norm_cat(s):
        if s.startswith("pok"): return "pokemon"
        if s.startswith("train"): return "trainer"
        if s.startswith("energ"): return "energy"
        return s

    rows = []
    for key in total_copies:
        cat = norm_cat(section_of[key])
        incl = round(100 * deck_count[key] / decks_analyzed, 1)
        if args.categoria and cat != args.categoria:
            continue
        if incl < args.min_inclusione:
            continue
        rows.append({
            "carta": display_name[key],
            "chiave": key,
            "categoria": cat,
            "rarita": "",  # riempita dopo se --rarity
            "set": setnum_of[key][0],
            "numero": setnum_of[key][1],
            "copie_totali": total_copies[key],
            "deck_che_la_giocano": deck_count[key],
            "inclusione_%": incl,
            "media_copie_per_deck": round(total_copies[key] / deck_count[key], 2),
        })
    rows.sort(key=lambda r: (r["deck_che_la_giocano"], r["copie_totali"]), reverse=True)

    if args.rarity:
        print(f"\nArricchisco la rarita di {len(rows)} carte (uso cache {CACHE_FILE})...", file=sys.stderr)
        cache = load_cache()
        for i, r in enumerate(rows, 1):
            r["rarita"] = fetch_rarity(session, r["set"], r["numero"], cache, args.card_delay)
            if i % 25 == 0:
                save_cache(cache)
                print(f"    {i}/{len(rows)}", file=sys.stderr)
        save_cache(cache)

    with open(f"{args.out_prefix}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with open(f"{args.out_prefix}.json", "w", encoding="utf-8") as f:
        json.dump({"meta": {"game": args.game, "format": args.format,
                            "tornei_analizzati": len(tournaments), "deck_analizzati": decks_analyzed},
                   "cards": rows}, f, ensure_ascii=False, indent=2)

    print(f"\nDeck analizzati: {decks_analyzed}")
    print(f"Carte mostrate: {len(rows)}")
    print(f"\nTop {args.top} carte per numero di deck che le giocano:\n")
    header = f"{'#':>3}  {'carta':34s} {'cat':9s}"
    if args.rarity:
        header += f" {'rarita':18s}"
    header += f" {'incl.%':>7} {'deck':>6} {'copie':>7}"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(rows[:args.top], 1):
        line = f"{i:>3}  {r['carta'][:34]:34s} {r['categoria']:9s}"
        if args.rarity:
            line += f" {r['rarita'][:18]:18s}"
        line += f" {r['inclusione_%']:>6}% {r['deck_che_la_giocano']:>6} {r['copie_totali']:>7}"
        print(line)
    print(f"\nSalvati: {args.out_prefix}.csv e {args.out_prefix}.json", file=sys.stderr)


if __name__ == "__main__":
    main()