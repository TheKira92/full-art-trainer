#!/usr/bin/env python3
"""
gen_tracker.py
--------------
Genera un tracker HTML autonomo a partire da un CSV prodotto da
limitless_fullart.py (colonne: set, numero, lingua, url_carta,
url_immagine, url_immagine_grande).

Versione SOLO INGLESE: i set vengono messi in un'unica lista in ordine
cronologico (dal piu recente al piu vecchio). Eventuali righe non inglesi
nel CSV vengono ignorate.

Uso:
  python gen_tracker.py                      # legge fullart.csv -> docs/index.html
  python gen_tracker.py miocsv.csv           # csv diverso
  python gen_tracker.py fullart.csv out.html # csv e output diversi

Genera/garantisce anche i file PWA (manifest.webmanifest, sw.js, icone,
.nojekyll). I file accessori NON vengono mai sovrascritti: se vuoi
rigenerarli da zero, cancellali prima di rilanciare lo script.
"""
import csv, json, os, re, sys
from pathlib import Path

# Ordine cronologico dei set inglesi (recente -> vecchio), da limitlesstcg.com/cards
CHRONO_EN = ["CRI","POR","ASC","PFL","MEG","MEE","MEP","BLK","WHT","DRI","JTG","PRE",
"SSP","SCR","SFA","TWM","TEF","PAF","PAR","MEW","OBF","PAL","SVI","SVE","SVP",
"CRZ","SIT","LOR","PGO","ASR","BRS","FST","CEL","EVS","CRE","BST","SHF","VIV",
"CPA","DAA","RCL","SSH","SP","CEC","HIF","UNM","UNB","DET","TEU","LOT","DRM",
"CES","FLI","UPR","CIN","SLG","BUS","GRI","SUM","SMP","EVO","STS","FCO","GEN",
"BKP","BKT","AOR","ROS","DCR","PRC","PHF","FFI","FLF","XY","KSS","XYP","LTR",
"PLB","PLF","PLS","BCR","DRV","NVI"]
rank = {c:i for i,c in enumerate(CHRONO_EN)}

csv_path = sys.argv[1] if len(sys.argv) > 1 else "fullart.csv"
out_path = sys.argv[2] if len(sys.argv) > 2 else "docs/index.html"

try:
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
except FileNotFoundError:
    print(f"ERRORE: non trovo '{csv_path}'. Lancia prima limitless_fullart.py "
          f"oppure indica il percorso del CSV.", file=sys.stderr)
    sys.exit(1)

# tieni solo le carte inglesi (se la colonna lingua esiste)
kept, skipped = [], 0
for r in rows:
    if r.get("lingua", "en") in ("en", ""):
        kept.append(r)
    else:
        skipped += 1
if skipped:
    print(f"Ignorate {skipped} righe non inglesi.", file=sys.stderr)

cards = [{"id": f"{r['set']}-{r['numero']}", "s": r["set"], "n": r["numero"],
          "img": r["url_immagine"]} for r in kept]

def numkey(n):
    m = re.match(r"^(\d+)", n)
    return (0, int(m.group(1)), n) if m else (1, 0, n)

cards.sort(key=lambda c: (rank.get(c["s"], 9999), numkey(c["n"])))
unknown = sorted(set(c["s"] for c in cards if c["s"] not in rank))
if unknown:
    print(f"Set senza posizione cronologica (vanno in fondo): {unknown}", file=sys.stderr)

data_js = json.dumps(cards, ensure_ascii=False, separators=(",", ":"))

# -- PWA: bump questa stringa per forzare un refresh del service worker -------
PWA_VERSION = "v1"
THEME = "#1e1e2e"
ACCENT = "#a6e3a1"

HTML = r'''<!DOCTYPE html>
<html lang="it"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1,viewport-fit=cover">
<title>Full Art Trainer · Collezione</title>
<link rel="manifest" href="./manifest.webmanifest">
<meta name="theme-color" content="#1e1e2e">
<link rel="icon" type="image/png" sizes="192x192" href="./icons/icon-192.png">
<link rel="apple-touch-icon" href="./icons/icon-192.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="FA Trainer">
<style>
  :root{--base:#1e1e2e;--mantle:#181825;--crust:#11111b;--surface0:#313244;
    --surface1:#45475a;--text:#cdd6f4;--subtext:#a6adc8;--overlay:#6c7086;
    --green:#a6e3a1;--green-dim:#5a7a55;--maroon:#eba0ac;
    --mono:'JetBrains Mono',ui-monospace,'Cascadia Code',monospace;
    --sans:ui-sans-serif,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--base);color:var(--text);font-family:var(--sans);-webkit-font-smoothing:antialiased;padding-bottom:4rem}
  header{position:sticky;top:0;z-index:20;background:rgba(24,24,37,.92);backdrop-filter:blur(10px);
    border-bottom:1px solid var(--surface0);padding:1.1rem clamp(1rem,4vw,2.5rem) .9rem;padding-top:calc(1.1rem + env(safe-area-inset-top))}
  .titlerow{display:flex;align-items:baseline;gap:.7rem;flex-wrap:wrap}
  h1{font-size:1.3rem;font-weight:800;letter-spacing:-.02em}h1 .accent{color:var(--green)}
  .subtitle{font-family:var(--mono);font-size:.76rem;color:var(--overlay)}
  .progress-wrap{margin-top:.8rem;display:flex;align-items:center;gap:1rem}
  .bar{flex:1;height:10px;background:var(--surface0);border-radius:999px;overflow:hidden}
  .bar-fill{height:100%;width:0;background:linear-gradient(90deg,var(--green-dim),var(--green));
    border-radius:999px;transition:width .45s cubic-bezier(.22,1,.36,1)}
  .count{font-family:var(--mono);font-size:.9rem;font-weight:600;white-space:nowrap}
  .count b{color:var(--green);font-size:1.02rem}.pct{color:var(--overlay)}
  .toolbar{display:flex;gap:.6rem;flex-wrap:wrap;align-items:center;padding:.9rem clamp(1rem,4vw,2.5rem);
    border-bottom:1px solid var(--surface0);position:sticky;top:118px;z-index:15;
    background:rgba(30,30,46,.92);backdrop-filter:blur(8px)}
  .seg{display:inline-flex;background:var(--surface0);border-radius:9px;padding:3px}
  .seg button{font-family:var(--sans);font-size:.8rem;font-weight:600;color:var(--subtext);
    background:none;border:none;padding:.4rem .8rem;border-radius:7px;cursor:pointer;transition:.15s}
  .seg button.active{background:var(--green);color:var(--crust)}
  select,input[type=search]{font-family:var(--sans);font-size:.8rem;color:var(--text);
    background:var(--surface0);border:1px solid var(--surface1);border-radius:8px;padding:.42rem .7rem;outline:none}
  input[type=search]{min-width:140px}select:focus,input:focus{border-color:var(--green)}
  .spacer{flex:1}
  .btn{font-family:var(--sans);font-size:.78rem;font-weight:600;cursor:pointer;background:var(--surface0);
    color:var(--subtext);border:1px solid var(--surface1);border-radius:8px;padding:.42rem .8rem;transition:.15s}
  .btn:hover{color:var(--text);border-color:var(--overlay)}.btn.danger:hover{color:var(--maroon);border-color:var(--maroon)}
  main{padding:1.4rem clamp(1rem,4vw,2.5rem)}
  .setgroup{margin-bottom:2rem}
  .sethead{display:flex;align-items:center;gap:.7rem;margin-bottom:.8rem;padding-bottom:.4rem;border-bottom:1px dashed var(--surface1)}
  .setcode{font-family:var(--mono);font-weight:700;font-size:1rem;color:var(--text);background:var(--surface0);padding:.15rem .55rem;border-radius:6px}
  .setbadge{font-family:var(--mono);font-size:.78rem;color:var(--subtext)}.setbadge.done{color:var(--green)}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:.85rem}
  .card{position:relative;cursor:pointer;border-radius:10px;overflow:hidden;background:var(--mantle);
    border:2px solid transparent;transition:transform .14s ease,border-color .14s ease,box-shadow .14s ease}
  .card img{width:100%;display:block;aspect-ratio:734/1024;object-fit:cover;filter:grayscale(.85) brightness(.55);opacity:.7;transition:.22s}
  .card .tag{font-family:var(--mono);font-size:.66rem;color:var(--subtext);text-align:center;padding:.3rem .2rem;background:var(--mantle)}
  .card .check{position:absolute;top:6px;right:6px;width:22px;height:22px;border-radius:50%;background:var(--surface1);
    display:grid;place-items:center;opacity:0;transform:scale(.6);transition:.18s;box-shadow:0 2px 6px rgba(0,0,0,.4)}
  .card .check svg{width:13px;height:13px;stroke:var(--crust);stroke-width:3.5;fill:none;stroke-linecap:round;stroke-linejoin:round}
  .card:hover{transform:translateY(-3px)}.card:hover img{opacity:.85}
  .card.owned{border-color:var(--green);box-shadow:0 0 0 1px var(--green),0 6px 18px rgba(166,227,161,.13)}
  .card.owned img{filter:none;opacity:1}.card.owned .tag{color:var(--green)}
  .card.owned .check{opacity:1;transform:scale(1);background:var(--green)}
  .empty{text-align:center;color:var(--overlay);font-family:var(--mono);padding:4rem 1rem;font-size:.95rem}
  .toast{position:fixed;bottom:1.2rem;left:50%;transform:translateX(-50%) translateY(2rem);background:var(--surface1);
    color:var(--text);font-family:var(--mono);font-size:.8rem;padding:.55rem 1rem;border-radius:9px;opacity:0;
    transition:.25s;pointer-events:none;z-index:40}.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
  @media(max-width:520px){.toolbar{top:128px}.grid{grid-template-columns:repeat(auto-fill,minmax(98px,1fr));gap:.6rem}}
</style></head><body>
<header>
  <div class="titlerow"><h1>Full Art <span class="accent">Trainer</span></h1>
    <span class="subtitle">tracker collezione · EN · Limitless DB</span></div>
  <div class="progress-wrap"><div class="bar"><div class="bar-fill" id="barFill"></div></div>
    <div class="count"><b id="ownedN">0</b> / <span id="totalN">0</span> <span class="pct" id="pctN">(0%)</span></div></div>
</header>
<div class="toolbar">
  <div class="seg" id="filterSeg"><button data-f="all" class="active">Tutte</button>
    <button data-f="owned">Possedute</button><button data-f="missing">Mancanti</button></div>
  <select id="setSel"><option value="">Tutti i set</option></select>
  <input type="search" id="search" placeholder="Cerca set o numero...">
  <span class="spacer"></span>
  <button class="btn" id="importBtn">Importa</button>
  <button class="btn" id="exportBtn">Esporta</button>
  <button class="btn danger" id="resetBtn">Azzera</button>
  <input type="file" id="importFile" accept="application/json" style="display:none">
</div>
<main id="main"></main><div class="toast" id="toast"></div>
<script>
const CARDS = __DATA__;
const STORAGE_KEY = 'fullart-trainer-en';
let owned=new Set(), filter='all', setFilter='', query='';
function loadOwned(){ try{ const ls=localStorage.getItem(STORAGE_KEY); if(ls) owned=new Set(JSON.parse(ls)); }catch(e){} }
let saveTimer=null;
function saveOwned(){ clearTimeout(saveTimer); saveTimer=setTimeout(()=>{ try{ localStorage.setItem(STORAGE_KEY, JSON.stringify([...owned])); }catch(e){} },200); }
const main=document.getElementById('main');
function setsOrdered(){ const o=[],s=new Set(); for(const c of CARDS){ if(!s.has(c.s)){s.add(c.s);o.push(c.s);} } return o; }
function populateSetSelect(){ const sel=document.getElementById('setSel'),cnt={};
  for(const c of CARDS) cnt[c.s]=(cnt[c.s]||0)+1;
  for(const s of setsOrdered()){ const o=document.createElement('option'); o.value=s; o.textContent=s+' ('+cnt[s]+')'; sel.appendChild(o); } }
function matches(c){ if(setFilter&&c.s!==setFilter)return false;
  if(filter==='owned'&&!owned.has(c.id))return false; if(filter==='missing'&&owned.has(c.id))return false;
  if(query){ const q=query.toLowerCase(); if(!(c.s.toLowerCase().includes(q)||c.n.toLowerCase().includes(q)))return false; } return true; }
function render(){ const vis=CARDS.filter(matches); main.innerHTML='';
  if(!vis.length){ main.innerHTML='<div class="empty">Nessuna carta con questi filtri.</div>'; return; }
  const g={}; for(const c of vis)(g[c.s]=g[c.s]||[]).push(c);
  for(const s of setsOrdered()){ if(!g[s])continue;
    const oin=CARDS.filter(c=>c.s===s&&owned.has(c.id)).length, tin=CARDS.filter(c=>c.s===s).length, done=oin===tin;
    const sec=document.createElement('section'); sec.className='setgroup';
    sec.innerHTML='<div class="sethead"><span class="setcode">'+s+'</span><span class="setbadge '+(done?'done':'')+'">'+oin+'/'+tin+(done?' ✓':'')+'</span></div>';
    const grid=document.createElement('div'); grid.className='grid';
    for(const c of g[s]){ const el=document.createElement('div'); el.className='card'+(owned.has(c.id)?' owned':'');
      el.innerHTML='<div class="check"><svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg></div>'+
        '<img loading="lazy" referrerpolicy="no-referrer" src="'+c.img+'" alt="'+c.id+'" onerror="this.style.opacity=.15;this.alt=\'img n/d\'">'+
        '<div class="tag">'+c.s+' · '+c.n+'</div>';
      el.addEventListener('click',()=>toggle(c.id,el)); grid.appendChild(el); }
    sec.appendChild(grid); main.appendChild(sec); } }
function updateStats(){ const n=owned.size,t=CARDS.length,p=t?Math.round(n/t*100):0;
  document.getElementById('ownedN').textContent=n; document.getElementById('totalN').textContent=t;
  document.getElementById('pctN').textContent='('+p+'%)'; document.getElementById('barFill').style.width=p+'%'; }
function toggle(id,el){ if(owned.has(id)){owned.delete(id);el.classList.remove('owned');}else{owned.add(id);el.classList.add('owned');}
  updateStats(); saveOwned(); if(filter!=='all') setTimeout(render,180); }
function toast(m){ const t=document.getElementById('toast'); t.textContent=m; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),1600); }
document.getElementById('filterSeg').addEventListener('click',e=>{ const b=e.target.closest('button'); if(!b)return;
  document.querySelectorAll('#filterSeg button').forEach(x=>x.classList.remove('active')); b.classList.add('active'); filter=b.dataset.f; render(); });
document.getElementById('setSel').addEventListener('change',e=>{setFilter=e.target.value;render();});
document.getElementById('search').addEventListener('input',e=>{query=e.target.value.trim();render();});
document.getElementById('resetBtn').addEventListener('click',()=>{ if(!owned.size){toast('Niente da azzerare');return;}
  if(confirm('Azzerare le '+owned.size+' carte segnate?')){owned.clear();updateStats();saveOwned();render();toast('Azzerato');} });
document.getElementById('exportBtn').addEventListener('click',()=>{ const d={owned:[...owned],totale:CARDS.length,aggiornato:new Date().toISOString()};
  const b=new Blob([JSON.stringify(d,null,2)],{type:'application/json'}); const a=document.createElement('a');
  a.href=URL.createObjectURL(b); a.download='collezione-fullart-trainer.json'; a.click(); toast('Esportato'); });
document.getElementById('importBtn').addEventListener('click',()=>document.getElementById('importFile').click());
document.getElementById('importFile').addEventListener('change',e=>{ const f=e.target.files[0]; if(!f)return; const r=new FileReader();
  r.onload=()=>{ try{ const d=JSON.parse(r.result); const arr=Array.isArray(d)?d:(d.owned||[]); owned=new Set(arr);
    updateStats(); saveOwned(); render(); toast('Importate '+owned.size+' carte'); }catch(err){ toast('File non valido'); } };
  r.readAsText(f); e.target.value=''; });
loadOwned(); document.getElementById('totalN').textContent=CARDS.length; populateSetSelect(); updateStats(); render();
if('serviceWorker' in navigator){
  window.addEventListener('load',()=>{
    navigator.serviceWorker.register('./sw.js',{scope:'./'})
      .catch(err=>console.warn('SW register failed:',err));
  });
}
</script></body></html>'''

HTML = HTML.replace("__DATA__", data_js)
# crea la cartella di output se serve (es. `docs/index.html` per GitHub Pages)
Path(out_path).resolve().parent.mkdir(parents=True, exist_ok=True)
open(out_path, "w", encoding="utf-8").write(HTML)
print(f"OK -> {out_path}  ({len(cards)} carte, {len(set(c['s'] for c in cards))} set)")

# ---------------------------------------------------------------------------
#  PWA: file accessori. Creati solo se mancanti (non si sovrascrivono mai).
# ---------------------------------------------------------------------------
out_dir = Path(out_path).resolve().parent
html_name = Path(out_path).name

MANIFEST = {
    "name": "Full Art Trainer",
    "short_name": "FA Trainer",
    "description": "Tracker collezione carte Pokémon Full Art (Limitless DB).",
    "lang": "it",
    "dir": "ltr",
    "start_url": f"./{html_name}",
    "scope": "./",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": THEME,
    "theme_color": THEME,
    "icons": [
        {"src": "./icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "./icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "./icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

# Lista dei file same-origin che il SW deve precachare.
# (i path sono relativi alla scope dir, sw.js li userà tali e quali)
PRECACHE = [
    "./",
    f"./{html_name}",
    "./manifest.webmanifest",
    "./icons/icon-192.png",
    "./icons/icon-512.png",
    "./icons/icon-maskable-512.png",
]

SW_JS = f"""// Service worker per Full Art Trainer (PWA)
// Generato da gen_tracker.py — modifica liberamente se vuoi, NON viene
// sovrascritto: per rigenerarlo cancella questo file e rilancia.
const CACHE_VERSION = '{PWA_VERSION}';
const STATIC_CACHE  = 'fa-trainer-static-' + CACHE_VERSION;
const IMG_CACHE     = 'fa-trainer-img-'    + CACHE_VERSION;

// File same-origin da precachare (relativi allo scope del SW).
const PRECACHE_URLS = {json.dumps(PRECACHE)};

// Host del CDN immagini di Limitless (cross-origin → opaque response).
const IMG_HOST = 'limitlesstcg.nyc3.cdn.digitaloceanspaces.com';

self.addEventListener('install', (event) => {{
  event.waitUntil((async () => {{
    const cache = await caches.open(STATIC_CACHE);
    // addAll fallisce in blocco se uno solo dei file manca: facciamo
    // i put uno alla volta in modo tollerante.
    await Promise.all(PRECACHE_URLS.map(async (url) => {{
      try {{
        const res = await fetch(url, {{ cache: 'reload' }});
        if (res.ok || res.type === 'opaque') await cache.put(url, res.clone());
      }} catch (_) {{ /* ignora: il file potrà essere recuperato a runtime */ }}
    }}));
    self.skipWaiting();
  }})());
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil((async () => {{
    const keep = new Set([STATIC_CACHE, IMG_CACHE]);
    for (const name of await caches.keys()) {{
      if (!keep.has(name)) await caches.delete(name);
    }}
    await self.clients.claim();
  }})());
}});

self.addEventListener('fetch', (event) => {{
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // 1) immagini del CDN Limitless → stale-while-revalidate (no-cors / opaque)
  if (url.host === IMG_HOST) {{
    event.respondWith(staleWhileRevalidate(req, IMG_CACHE));
    return;
  }}

  // 2) same-origin → cache-first con fallback rete (e fallback all'HTML
  //    radice per le navigation request, così offline non muore tutto)
  if (url.origin === self.location.origin) {{
    event.respondWith(cacheFirst(req, STATIC_CACHE));
    return;
  }}

  // 3) altro: bypass
}});

async function cacheFirst(req, cacheName) {{
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req, {{ ignoreSearch: false }});
  if (hit) return hit;
  try {{
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  }} catch (err) {{
    if (req.mode === 'navigate') {{
      const fallback = await cache.match({json.dumps('./' + html_name)});
      if (fallback) return fallback;
    }}
    throw err;
  }}
}}

async function staleWhileRevalidate(req, cacheName) {{
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  // Per il CDN cross-origin usiamo no-cors: la response sarà 'opaque'
  // (status 0) ma può comunque essere messa in cache e servita.
  const fetchReq = new Request(req.url, {{ mode: 'no-cors', credentials: 'omit' }});
  const network = fetch(fetchReq).then((res) => {{
    if (res && (res.ok || res.type === 'opaque')) {{
      cache.put(req, res.clone()).catch(() => {{}});
    }}
    return res;
  }}).catch(() => null);
  return cached || (await network) || Response.error();
}}
"""


def write_if_missing(path: Path, content, *, binary=False) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if binary else "w"
    if binary:
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return True


# --- icone (Catppuccin Mocha: base #1e1e2e, accento verde #a6e3a1) -----------
def make_icons(icon_dir: Path) -> list[str]:
    created = []
    targets = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-512.png", 512, True),
    ]
    if all((icon_dir / name).exists() for name, _, _ in targets):
        return created
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # Fallback: ImageMagick CLI.
        import shutil, subprocess
        if not (shutil.which("magick") or shutil.which("convert")):
            print("ATTENZIONE: Pillow non disponibile e ImageMagick assente. "
                  "Salto la generazione delle icone.", file=sys.stderr)
            return created
        return _make_icons_with_imagemagick(icon_dir, targets)

    icon_dir.mkdir(parents=True, exist_ok=True)
    bg = (30, 30, 46, 255)           # #1e1e2e
    fg = (166, 227, 161, 255)        # #a6e3a1
    fg_dim = (90, 122, 85, 255)      # #5a7a55

    for name, size, maskable in targets:
        path = icon_dir / name
        if path.exists():
            continue
        img = Image.new("RGBA", (size, size), bg)
        draw = ImageDraw.Draw(img)

        # Per le icone maskable il contenuto va dentro un "safe zone" di
        # ~80% del canvas (spec PWA), perché i launcher Android possono
        # ritagliare ai bordi.
        safe = 0.8 if maskable else 1.0
        cx, cy = size / 2, size / 2
        outer_r = size * 0.42 * safe
        ring_w = max(2, size * 0.055 * safe)

        # cerchio esterno (accento)
        draw.ellipse(
            [cx - outer_r, cy - outer_r, cx + outer_r, cy + outer_r],
            outline=fg, width=int(ring_w),
        )
        # arco/quadrante in basso più scuro (effetto pokéball stilizzata)
        inner_r = outer_r - ring_w / 2
        draw.rectangle(
            [cx - inner_r, cy, cx + inner_r, cy + inner_r],
            fill=fg_dim,
        )
        # banda orizzontale al centro
        band_h = max(2, size * 0.045 * safe)
        draw.rectangle(
            [cx - outer_r - 2, cy - band_h / 2, cx + outer_r + 2, cy + band_h / 2],
            fill=fg,
        )
        # pallino centrale
        pin_r = size * 0.085 * safe
        draw.ellipse(
            [cx - pin_r, cy - pin_r, cx + pin_r, cy + pin_r],
            fill=bg, outline=fg, width=int(ring_w),
        )

        img.save(path, "PNG", optimize=True)
        created.append(name)
    return created


def _make_icons_with_imagemagick(icon_dir: Path, targets) -> list[str]:
    import subprocess, shutil
    icon_dir.mkdir(parents=True, exist_ok=True)
    cmd_base = "magick" if shutil.which("magick") else "convert"
    created = []
    for name, size, maskable in targets:
        path = icon_dir / name
        if path.exists():
            continue
        safe = 0.8 if maskable else 1.0
        cx = cy = size / 2
        r = size * 0.42 * safe
        pin_r = size * 0.085 * safe
        draws = [
            f"fill '#1e1e2e' rectangle 0,0 {size},{size}",
            f"stroke '#a6e3a1' stroke-width {max(2, int(size*0.055*safe))} fill none "
            f"circle {cx},{cy} {cx+r},{cy}",
            f"fill '#5a7a55' stroke none rectangle {cx-r:.0f},{cy:.0f} {cx+r:.0f},{cy+r:.0f}",
            f"fill '#a6e3a1' rectangle {cx-r-2:.0f},{cy-size*0.022*safe:.0f} "
            f"{cx+r+2:.0f},{cy+size*0.022*safe:.0f}",
            f"fill '#1e1e2e' stroke '#a6e3a1' stroke-width {max(2,int(size*0.055*safe))} "
            f"circle {cx},{cy} {cx+pin_r},{cy}",
        ]
        subprocess.run(
            [cmd_base, "-size", f"{size}x{size}", "xc:none",
             "-draw", " ".join(draws), str(path)],
            check=True,
        )
        created.append(name)
    return created


# --- write artefatti --------------------------------------------------------
created_any = []

if write_if_missing(out_dir / "manifest.webmanifest",
                    json.dumps(MANIFEST, ensure_ascii=False, indent=2)):
    created_any.append("manifest.webmanifest")

if write_if_missing(out_dir / "sw.js", SW_JS):
    created_any.append("sw.js")

if write_if_missing(out_dir / ".nojekyll", ""):
    created_any.append(".nojekyll")

icons_created = make_icons(out_dir / "icons")
created_any.extend(f"icons/{n}" for n in icons_created)

if created_any:
    print("PWA: creati " + ", ".join(created_any))
else:
    print("PWA: tutti i file accessori erano già presenti (nessuna sovrascrittura).")
