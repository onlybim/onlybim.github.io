#!/usr/bin/env python3
"""Met à jour la liste des vidéos de index.html à partir de la chaîne YouTube OnlyBim.

Utilise l'API YouTube Data v3 (clé dans la variable d'environnement YOUTUBE_API_KEY).
Ne touche qu'à trois choses dans index.html :
  - la liste des miniatures  var V=[[id, titre, durée], ...];
  - le compteur  <span id="nbvid">N</span>
  - la liste des pastilles « Déjà filmé »  var S=[[id, libellé court], ...];
Si quoi que ce soit semble anormal, le fichier n'est PAS modifié.
"""
import json, os, re, sys, urllib.parse, urllib.request

CHANNEL_ID = "UCTEBEqyBe2bzaXNAz3-7LKw"
UPLOADS = "UU" + CHANNEL_ID[2:]          # liste « Mises en ligne » de la chaîne
INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html")
API = "https://www.googleapis.com/youtube/v3/"


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


def fetch_videos():
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
            out[v["id"]] = (v["id"], v["snippet"]["title"], dur, v["snippet"]["publishedAt"])
    # plus récentes d'abord
    return sorted(out.values(), key=lambda x: x[3], reverse=True)


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
    for i, t, _d, _p in vids:
        if i in LABELS:
            out.append((i, LABELS[i]))
        elif re.search(r"\d+/10\b", t):      # parties d'une série : une seule pastille (déjà dans LABELS)
            continue
        else:
            out.append((i, short_label(t)))
    return out


def js_str(s):
    return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")


def main():
    vids = fetch_videos()
    if len(vids) < 10:
        sys.exit(f"Seulement {len(vids)} vidéos reçues : on ne touche à rien.")
    html = open(INDEX, encoding="utf8").read()

    new_list = "var V=[" + ", ".join(
        f"[{js_str(i)}, {js_str(t)}, {js_str(d)}]" for i, t, d, _ in vids) + "];"
    html2, n1 = re.subn(r"var V=\[\[.*?\]\];", lambda m: new_list, html, count=1, flags=re.S)
    new_chips = "var S=[" + ",".join(
        f"[{js_str(i)},{js_str(l)}]" for i, l in chips(vids)) + "];"
    html2, n2 = re.subn(r'(<span id="nbvid">)\d+(</span>)', lambda m: f"{m.group(1)}{len(vids)}{m.group(2)}", html2, count=1)
    html2, n3 = re.subn(r"var S=\[\[.*?\]\];", lambda m: new_chips, html2, count=1, flags=re.S)
    if n1 != 1 or n2 != 1 or n3 != 1:
        sys.exit("Repères introuvables dans index.html : on ne touche à rien.")
    if html2 == html:
        print("Déjà à jour.")
        return
    open(INDEX, "w", encoding="utf8").write(html2)
    print(f"Mis à jour : {len(vids)} vidéos.")


if __name__ == "__main__":
    main()
