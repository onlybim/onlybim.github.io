#!/usr/bin/env python3
"""Met à jour la liste des vidéos de index.html à partir de la chaîne YouTube OnlyBim.

Utilise l'API YouTube Data v3 (clé dans la variable d'environnement YOUTUBE_API_KEY).
Ne touche qu'à trois choses dans index.html :
  - la liste  var V=[[id, titre, durée], ...];
  - le compteur  <span id="nbvid">N</span>
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
    html2, n2 = re.subn(r'(<span id="nbvid">)\d+(</span>)', lambda m: f"{m.group(1)}{len(vids)}{m.group(2)}", html2, count=1)
    if n1 != 1 or n2 != 1:
        sys.exit("Repères introuvables dans index.html : on ne touche à rien.")
    if html2 == html:
        print("Déjà à jour.")
        return
    open(INDEX, "w", encoding="utf8").write(html2)
    print(f"Mis à jour : {len(vids)} vidéos.")


if __name__ == "__main__":
    main()
