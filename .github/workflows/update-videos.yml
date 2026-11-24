name: Mise à jour des vidéos YouTube

on:
  schedule:
    - cron: "17 10 * * *"   # tous les jours, vers 5 h 17 à Montréal
  workflow_dispatch:         # permet aussi de le lancer à la main

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Lire la chaîne YouTube et mettre à jour index.html
        env:
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}
        run: python3 scripts/update_videos.py
      - name: Enregistrer s'il y a du nouveau
        run: |
          if [ -n "$(git status --porcelain index.html)" ]; then
            git config user.name "OnlyBim bot"
            git config user.email "actions@users.noreply.github.com"
            git add index.html
            git commit -m "Mise à jour automatique des vidéos YouTube"
            git push
          else
            echo "Rien de nouveau."
          fi
