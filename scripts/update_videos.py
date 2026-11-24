#!/usr/bin/env python3
"""Synchronise le site OnlyBim avec la chaîne YouTube.

Utilise l'API YouTube Data v3 (clé dans la variable d'environnement YOUTUBE_API_KEY).

Ce que le script met à jour :
  - index.html : la liste des miniatures  var V=[...];
                 le compteur  <span id="nbvid">N</span>
                 la liste des pastilles « Déjà filmé »  var S=[...];
  - tutoriels.html : la page complète « Tous les tutoriels » (réécrite à chaque fois)
  - sitemap.xml : le plan du site, avec la date de la vidéo la plus récente

Si quoi que ce soit semble anormal, rien n'est modifié.
"""
import html as H
import json, os, re, sys, urllib.parse, urllib.request

CHANNEL_ID = "UCTEBEqyBe2bzaXNAz3-7LKw"
UPLOADS = "UU" + CHANNEL_ID[2:]          # liste « Mises en ligne » de la chaîne
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
INDEX = os.path.join(ROOT, "index.html")
TUTOS = os.path.join(ROOT, "tutoriels.html")
SITEMAP = os.path.join(ROOT, "sitemap.xml")
SITE = "https://onlybim.ca"
API = "https://www.googleapis.com/youtube/v3/"
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def call(endpoint, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def fmt_duration(iso):
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return None
    h, mi, s = (int(x or 0) for x in m.groups())
    return f"{h}:{mi:02d}:{s:02d}" if h else f"{mi}:{s:02d}"


def intro_from_description(desc):
    """Prend le paragraphe « Dans cette vidéo, … » de la description YouTube (s'il existe)."""
    for para in re.split(r"\n\s*\n", desc or ""):
        p = " ".join(para.split())
        if p.lower().startswith("dans cette vidéo"):
            if len(p) > 230:
                p = p[:230].rsplit(" ", 1)[0].rstrip(",;: ") + "…"
            return p
    return ""


def fetch_videos():
    """Retourne une liste de dicts (id, title, dur, published, desc), plus récentes d'abord."""
    ids, token = [], None
    while True:
        p = dict(part="contentDetails", playlistId=UPLOADS, maxResults=50)
        if token:
            p["pageToken"] = token
        d = call("playlistItems", **p)
        ids += [i["contentDetails"]["videoId"] for i in d.get("items", [])]
        token = d.get("nextPageToken")
        if not token:
            break
    out = {}
    for k in range(0, len(ids), 50):
        d = call("videos", part="snippet,contentDetails,status", id=",".join(ids[k:k + 50]))
        for v in d.get("items", []):
            if v["status"].get("privacyStatus") != "public":
                continue
            dur = fmt_duration(v["contentDetails"].get("duration"))
            if not dur or dur == "0:00":
                continue
            out[v["id"]] = dict(id=v["id"], title=v["snippet"]["title"], dur=dur,
                                published=v["snippet"]["publishedAt"],
                                desc=intro_from_description(v["snippet"].get("description")))
    return sorted(out.values(), key=lambda x: x["published"], reverse=True)


# Libellés courts des pastilles « Déjà filmé ».
# Pour une vidéo absente de cette liste, le script fabrique un libellé à partir du titre.
# Pour corriger un libellé : ajoute ou modifie une ligne  "id": "Libellé",  ci-dessous.
LABELS = {
    "kagK-v3rUSY": "Poteaux porteurs",
    "bjsTUxyU4Dk": "Semelle en gradin",
    "60UFE4fg9H4": "Fichier central",
    "a8ypgDrK4vI": "Ligne de justification",
    "WSURkrZhwvs": "Famille pour débutants",
    "WnkCH2lmFBY": "Famille paramétrique (cercle)",
    "DOTWjttnH90": "Élément de détail paramétrique",
    "k4PaeYdWKkc": "Formules dans une famille",
    "XXU5dvdoG9I": "Visibilité et formule IF",
    "DXsTtZ1gJ4Q": "Ligne de titre trop longue",
    "tlafMB0ZWRY": "Murs structuraux",
    "MW4TaaKUj9Y": "Mur structural ou architectural",
    "I-A1JfL8iwQ": "Créer un mur",
    "C9DzMV1-_lA": "Niveaux",
    "2vmBNYGAow8": "Détacher un modèle",
    "aAkswXhFFnQ": "Ouvrir un modèle existant",
    "4dGIZkxUq6Q": "Dalle sur des murs",
    "qCQc2LV4Zjk": "Sièges de poutrelles",
    "K2Pi35TEjDQ": "Semelle porteuse",
    "hyVFFmvxIig": "Semelle porteuse vs de soutènement",
}


def short_label(title):
    t = re.sub(r"^\s*Revit\s*:\s*", "", title)          # « Revit : » au début
    t = re.sub(r"\([^)]*\)", "", t)                       # (tutoriel), (2024), (partie 2)
    t = re.split(r"\s:\s|[?,]", t)[0]                      # avant « : », « ? » ou « , »
    t = re.sub(r"\s+dans\s+Revit.*$", "", t, flags=re.I)  # « dans Revit 2026 »
    t = re.sub(r"\s+(Revit\s*)?(20\d\d)\s*$", "", t)     # année à la fin
    t = re.sub(r"\s+", " ", t).strip(" -–:")
    if len(t) > 38:
        t = t[:38].rsplit(" ", 1)[0]
    return (t[:1].upper() + t[1:]) or title[:38]


def chips(vids):
    out = []
    for v in vids:
        if v["id"] in LABELS:
            out.append((v["id"], LABELS[v["id"]]))
        elif re.search(r"\d+/10\b", v["title"]):      # parties d'une série : une seule pastille (déjà dans LABELS)
            continue
        else:
            out.append((v["id"], short_label(v["title"])))
    return out


def js_str(s):
    return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")


def date_fr(iso):
    y, m, d = iso[:10].split("-")
    return f"{int(d)} {MOIS[int(m) - 1]} {y}"


# ---------------------------------------------------------------- page « Tutoriels »
TUTOS_CSS = """
:root{--bg:#fff;--fg:#0F1A24;--muted:#55636F;--line:#E3E8EC;--accent:#0B73B8;--tint:#E4F2FA;--font:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:var(--font);font-size:16px;line-height:1.5}
a{color:inherit}
:focus-visible{outline:3px solid #2E9BDB;outline-offset:3px}
.wrap{max-width:1120px;margin:0 auto;padding-inline:16px}
h1,h2,h3{text-wrap:balance;letter-spacing:-.025em;margin:0}
header.top{border-bottom:1px solid var(--line)}
header.top .wrap{display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;align-items:center;padding-block:20px}
.logo{display:inline-flex;align-items:center;gap:10px;font-weight:700;font-size:26px;letter-spacing:-.02em;text-decoration:none}
.badge{display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:7px 14px;border-radius:999px;background:var(--tint);color:var(--accent)}
.badge i{width:8px;height:8px;border-radius:50%;background:currentColor}
.intro .wrap{padding-block:36px 8px;max-width:820px}
.intro h1{font-size:clamp(28px,4vw,42px);font-weight:800}
.intro p{color:#2F4452;font-size:18px;margin:12px 0 0}
.list{list-style:none;margin:0;padding:0;display:grid;gap:18px;padding-block:24px 40px}
.list li{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}
.card{display:grid;grid-template-columns:minmax(0,1fr);gap:12px;text-decoration:none;border:1px solid var(--line);border-radius:14px;padding:12px;transition:border-color .2s}
.card:hover,.card:focus-visible{border-color:var(--accent)}
.tb{position:relative;display:block;aspect-ratio:16/9;border-radius:10px;overflow:hidden;background:#0F1A24}
.tb img{width:100%;height:100%;object-fit:cover;display:block}
.dur{position:absolute;right:8px;bottom:8px;background:rgba(15,26,36,.88);color:#fff;font-style:normal;font-size:13px;font-weight:600;padding:2px 7px;border-radius:6px}
.card h2{font-size:18px;font-weight:700;letter-spacing:-.01em}
.meta{color:var(--muted);font-size:14px;margin:4px 0 0}
.card p{margin:8px 0 0;color:#2F4452;font-size:15px}
@media (min-width:720px){.card{grid-template-columns:320px minmax(0,1fr);gap:18px;align-items:start}}
.cta{background:var(--tint)}
.cta .wrap{padding-block:32px;display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between}
.cta h2{font-size:22px;font-weight:800}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 24px;border-radius:999px;font:700 15px var(--font);letter-spacing:.04em;text-decoration:none;background:var(--accent);color:#fff}
.btn.line{background:transparent;color:var(--fg);border:1.5px solid var(--fg)}
footer{padding-block:22px;color:var(--muted);font-size:14px}
footer a{color:inherit;text-decoration:underline;text-underline-offset:2px}
"""

LOGO = ('<a class="logo" href="/"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#0B73B8" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3" width="16" '
        'height="18" rx="2"/><path d="M10 9l5 3-5 3z" fill="#0B73B8"/></svg><span>Only<span style="color:#0B73B8">Bim</span></span></a>')


def build_tutos(vids):
    n = len(vids)
    title = "Tutoriels Revit en français : structure, familles, murs, dalles – OnlyBim"
    desc = (f"{n} tutoriels Revit gratuits en français : murs, poteaux, semelles, dalles, poutres, "
            "familles paramétriques et fichier central, par Amélie, experte BIM à Montréal.")
    items = []
    for v in vids:
        d = H.escape(v["desc"], quote=False)
        items.append(
            f'<li><a class="card" href="https://www.youtube.com/watch?v={v["id"]}" target="_blank" rel="noopener">'
            f'<span class="tb"><img src="https://i.ytimg.com/vi/{v["id"]}/mqdefault.jpg" alt="{H.escape(v["title"])}" '
            f'loading="lazy" width="320" height="180"><i class="dur">{v["dur"]}</i></span>'
            f'<div><h2>{H.escape(v["title"], quote=False)}</h2>'
            f'<p class="meta">{date_fr(v["published"])} · {v["dur"]} · OnlyBim</p>'
            + (f'<p>{d}</p>' if d else '') + '</div></a></li>')
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": "Tutoriels Revit en français",
          "numberOfItems": n,
          "itemListElement": [{"@type": "ListItem", "position": k + 1, "item": {
              "@type": "VideoObject", "name": v["title"],
              "description": v["desc"] or v["title"],
              "thumbnailUrl": f'https://i.ytimg.com/vi/{v["id"]}/hqdefault.jpg',
              "uploadDate": v["published"],
              "url": f'https://www.youtube.com/watch?v={v["id"]}',
              "embedUrl": f'https://www.youtube.com/embed/{v["id"]}'}} for k, v in enumerate(vids)]}
    return f"""<!DOCTYPE html>
<html lang="fr-CA">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{H.escape(title, quote=False)}</title>
<meta name="description" content="{H.escape(desc)}">
<link rel="canonical" href="{SITE}/tutoriels.html">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_CA">
<meta property="og:site_name" content="OnlyBim">
<meta property="og:url" content="{SITE}/tutoriels.html">
<meta property="og:title" content="{H.escape(title)}">
<meta property="og:description" content="{H.escape(desc)}">
<meta property="og:image" content="{SITE}/og-image.png">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}/og-image.png">
<script type="application/ld+json">{js_str_ld(ld)}</script>
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/icon-192.png" type="image/png" sizes="192x192">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap">
<style>{TUTOS_CSS}</style>
</head>
<body>
<header class="top"><div class="wrap">
  {LOGO}
  <span class="badge"><i></i>Tutoriels Revit gratuits</span>
</div></header>
<main>
<section class="intro"><div class="wrap">
  <h1>Tutoriels Revit en français</h1>
  <p>{n} tutoriels gratuits, en français, par Amélie, experte BIM à Montréal : structure (murs, poteaux, semelles, dalles, poutres), familles paramétriques et fichier central. Clique sur une vidéo pour la regarder sur YouTube.</p>
</div></section>
<div class="wrap"><ul class="list">
{chr(10).join(items)}
</ul></div>
<section class="cta"><div class="wrap">
  <h2>Un problème Revit ou BIM précis ?</h2>
  <a class="btn" href="/#contact">ÉCRIS-MOI</a>
</div></section>
</main>
<footer><div class="wrap">OnlyBim · onlybim.ca · <a href="/">Accueil</a> · <a href="https://www.youtube.com/channel/{CHANNEL_ID}" target="_blank" rel="noopener">Chaîne YouTube</a> · <a href="confidentialite-particulier.html">Politique de confidentialité</a></div></footer>
</body>
</html>
"""


def js_str_ld(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def build_sitemap(last):
    day = last[:10]
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{SITE}/</loc><lastmod>{day}</lastmod></url>
  <url><loc>{SITE}/tutoriels.html</loc><lastmod>{day}</lastmod></url>
  <url><loc>{SITE}/confidentialite-particulier.html</loc></url>
  <url><loc>{SITE}/confidentialite-entreprise.html</loc></url>
</urlset>
"""


def write_if_changed(path, text):
    old = open(path, encoding="utf8").read() if os.path.exists(path) else None
    if old == text:
        return False
    open(path, "w", encoding="utf8").write(text)
    return True


def main():
    vids = fetch_videos()
    if len(vids) < 10:
        sys.exit(f"Seulement {len(vids)} vidéos reçues : on ne touche à rien.")
    html = open(INDEX, encoding="utf8").read()

    new_list = "var V=[" + ", ".join(
        f"[{js_str(v['id'])}, {js_str(v['title'])}, {js_str(v['dur'])}]" for v in vids) + "];"
    html2, n1 = re.subn(r"var V=\[\[.*?\]\];", lambda m: new_list, html, count=1, flags=re.S)
    new_chips = "var S=[" + ",".join(
        f"[{js_str(i)},{js_str(l)}]" for i, l in chips(vids)) + "];"
    html2, n2 = re.subn(r'(<span id="nbvid">)\d+(</span>)', lambda m: f"{m.group(1)}{len(vids)}{m.group(2)}", html2, count=1)
    html2, n3 = re.subn(r"var S=\[\[.*?\]\];", lambda m: new_chips, html2, count=1, flags=re.S)
    if n1 != 1 or n2 != 1 or n3 != 1:
        sys.exit("Repères introuvables dans index.html : on ne touche à rien.")

    changed = []
    if write_if_changed(INDEX, html2):
        changed.append("index.html")
    if write_if_changed(TUTOS, build_tutos(vids)):
        changed.append("tutoriels.html")
    if write_if_changed(SITEMAP, build_sitemap(vids[0]["published"])):
        changed.append("sitemap.xml")
    print(("Mis à jour (" + ", ".join(changed) + f") : {len(vids)} vidéos.") if changed else "Déjà à jour.")


if __name__ == "__main__":
    main()
