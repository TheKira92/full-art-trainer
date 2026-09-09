#!/usr/bin/env python3
"""
fetch_names.py
--------------
Recupera i nomi delle carte (inglese + italiano) dal Card Database di
Limitless e li salva in una cache JSON, che gen_tracker.py usa per
rendere il tracker ricercabile per nome nelle due lingue.

Per ogni carta di fullart.csv visita /cards/{lingua}/{SET}/{NUM} e legge:
  - il nome della carta      (.card-text-name)
  - il nome dell'espansione  (.card-prints-current, es. "Buio Pesto (PBL)")

Il lavoro e' incrementale: le carte gia' in cache non vengono riscaricate,
quindi dopo una nuova espansione servono solo le richieste per le carte
nuove. Il file viene salvato ogni 25 carte, si puo' interrompere e
riprendere senza perdere nulla.

Dipendenze:
  pip install requests beautifulsoup4

Esempi:
  python fetch_names.py                    # aggiorna solo le carte mancanti
  python fetch_names.py --refresh          # riscarica tutto da zero
  python fetch_names.py --langs en,it,fr   # aggiungi altre lingue
"""

import argparse
import csv
import json
import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

SITE = "https://limitlesstcg.com"
NAMES_FILE = "fullart_names.json"


def load_names(path):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("cards", {})
            data.setdefault("sets", {})
            return data
        except Exception:
            pass
    return {"cards": {}, "sets": {}}


def save_names(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)


def fetch_one(session, lang, cset, number, timeout=30):
    """Ritorna (nome_carta, nome_espansione) per una carta in una lingua."""
    url = f"{SITE}/cards/{lang}/{cset}/{number}"
    resp = session.get(url, timeout=timeout)
    if resp.status_code != 200:
        return "", ""
    soup = BeautifulSoup(resp.text, "html.parser")

    name = ""
    el = soup.find(class_="card-text-name") or soup.find(class_="card-text-title")
    if el:
        name = re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()

    expansion = ""
    pr = soup.find(class_="card-prints-current") or soup.find(class_="prints-current-details")
    if pr:
        t = re.sub(r"\s+", " ", pr.get_text(" ", strip=True))
        # formato: "Buio Pesto (PBL) #108 - Ultra Rare"
        m = re.match(r"(.+?)\s*\(" + re.escape(cset) + r"\)", t)
        if m:
            expansion = m.group(1).strip()

    return name, expansion


def main():
    ap = argparse.ArgumentParser(description="Nomi carte EN/IT dal DB Limitless")
    ap.add_argument("--csv", default="fullart.csv", help="CSV prodotto da limitless_fullart.py")
    ap.add_argument("--out", default=NAMES_FILE, help=f"cache JSON (default: {NAMES_FILE})")
    ap.add_argument("--langs", default="en,it", help="lingue separate da virgola (default: en,it)")
    ap.add_argument("--delay", type=float, default=0.2, help="pausa tra le richieste")
    ap.add_argument("--refresh", action="store_true", help="riscarica anche cio' che e' gia' in cache")
    args = ap.parse_args()

    langs = [l.strip() for l in args.langs.split(",") if l.strip()]

    try:
        rows = list(csv.DictReader(open(args.csv, encoding="utf-8")))
    except FileNotFoundError:
        print(f"ERRORE: non trovo '{args.csv}'. Lancia prima limitless_fullart.py.",
              file=sys.stderr)
        sys.exit(1)

    data = load_names(args.out)
    cards, sets = data["cards"], data["sets"]

    # una sola riga per (set, numero): il CSV e' gia' solo inglese
    wanted, seen = [], set()
    for r in rows:
        key = f"{r['set']}-{r['numero']}"
        if key not in seen:
            seen.add(key)
            wanted.append((key, r["set"], r["numero"]))

    todo = []
    for key, cset, num in wanted:
        missing = [l for l in langs if args.refresh or not cards.get(key, {}).get(l)]
        if missing:
            todo.append((key, cset, num, missing))

    print(f"Carte nel CSV: {len(wanted)} | gia' in cache: {len(wanted) - len(todo)} | "
          f"da scaricare: {len(todo)} (lingue: {', '.join(langs)})", file=sys.stderr)
    if not todo:
        print("Niente da fare.", file=sys.stderr)
        return

    session = requests.Session()
    session.headers.update({"User-Agent": "limitless-fullart/1.0"})

    errors = 0
    for i, (key, cset, num, missing) in enumerate(todo, 1):
        entry = cards.setdefault(key, {})
        for lang in missing:
            try:
                name, expansion = fetch_one(session, lang, cset, num)
            except Exception as e:
                print(f"  errore {lang} {key}: {e}", file=sys.stderr)
                errors += 1
                continue
            if name:
                entry[lang] = name
            if expansion:
                sets.setdefault(cset, {})[lang] = expansion
            time.sleep(args.delay)
        if i % 25 == 0:
            save_names(args.out, data)
            print(f"    {i}/{len(todo)}", file=sys.stderr)

    save_names(args.out, data)

    # riepilogo: quante carte hanno il nome in ogni lingua
    print(f"\nSalvato: {args.out}")
    print(f"Carte in cache: {len(cards)} | set: {len(sets)}")
    for lang in langs:
        have = sum(1 for k, _, _ in wanted if cards.get(k, {}).get(lang))
        print(f"  nome {lang}: {have}/{len(wanted)}")
    if errors:
        print(f"  richieste fallite: {errors} (rilancia per riprovare)", file=sys.stderr)


if __name__ == "__main__":
    main()
