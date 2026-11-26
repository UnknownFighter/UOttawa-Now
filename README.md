# uOttawa Events (free, bilingual) - Step 1

A static website that lists uOttawa club events found in their public Instagram (and later TikTok) posts.
A Python script runs on GitHub's free servers every 6 hours, reads the posts, runs OCR on the images, finds
dates/times in English and French, and writes `site/data/events.json`. The website only reads that file.

## Why this stack (all $0)
| Need | Choice | Why |
|---|---|---|
| Hosting | **GitHub Pages** | Free, you already have GitHub, no extra account. Cloudflare Pages is equally free but is one more account. |
| Schedule | **GitHub Actions cron**, every 6 hours | Free (unlimited minutes on public repos; 2,000/month on private - we use roughly 600). Runs can start late; GitHub may pause schedules on repos with no activity for 60 days. |
| Data | **JSON files committed in the repo** | Nothing to set up, nothing to break, instant to load. Firebase would add keys, SDKs and quotas for no benefit yet. Revisit it when you add logins/event submissions. |
| Scraping | **instaloader** (Instagram), **yt-dlp** (TikTok) | Plain Python, much simpler than Selenium and far lighter on CI. |
| OCR | **Tesseract** | Free, open source, English + French, runs only in the scheduled job. |

## Folder map
```
config.yaml             <- accounts, categories, term-date override (the file you edit)
pipeline/run.py         <- main script;  sources/ = scrapers;  ocr.py;  dates.py + details.py + extract.py = extraction
pipeline/updates.py     <- cancelled/rescheduled/room-change follow-ups
pipeline/storage.py     <- JSON files + "delete old events" rules;  terms.py = school-year dates
site/                   <- the website (index.html, style.css, app.js, data/)
.github/workflows/update.yml  <- the schedule
```

## What to install (Windows; Mac notes in brackets)
1. **VS Code** (you have it). Add the extension "Python" (Microsoft) from the Extensions tab.
2. **Python 3.12**: https://www.python.org/downloads/ - tick **"Add python.exe to PATH"** in the installer. [Mac: `brew install python`]
3. **Git**: https://git-scm.com/download/win (accept defaults). [Mac: comes with Xcode tools]
4. *Optional, only to test OCR on your own computer:* **Tesseract** from https://github.com/UB-Mannheim/tesseract/wiki (tick French when installing). The scheduled job installs its own, so you can skip this.

## Accounts to create
- **GitHub** - you have one.
- *(Optional, later)* a dedicated Instagram account for the logged-in fallback. Do not use your personal account.
- Nothing else. No Firebase, no domain registrar, no credit card.

## Step by step
1. Unzip this folder, then in VS Code: **File > Open Folder** and pick it. Open a terminal: **Terminal > New Terminal**.
2. Create an isolated Python environment and install the packages:
   ```
   python -m venv .venv
   .venv\Scripts\activate          (Mac: source .venv/bin/activate)
   pip install -r requirements.txt
   ```
   If VS Code asks which interpreter to use, choose the one in `.venv`.
3. **Test with fake posts** (no internet needed):
   ```
   python -m pipeline.run --demo
   python -m http.server -d site 8000
   ```
   Open http://localhost:8000/?demo. You should see sample events (stop the server with Ctrl+C).
4. **Fill in config.yaml**: for each account add the club's full `name` and `acronym`, and check its `category`.
5. **Put it on GitHub**: create a new **public** repository (e.g. `uottawa-events`) on github.com with no README. Then in the terminal:
   ```
   git init
   git add .
   git commit -m "First version"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/uottawa-events.git
   git push -u origin main
   ```
6. On GitHub: **Settings > Pages > Build and deployment > Source = "GitHub Actions"**.
7. **Actions** tab > "Update events and deploy site" > **Run workflow**. When it finishes (a few minutes), your site is at
   `https://YOUR-USERNAME.github.io/uottawa-events/` - that is your free subdomain. From then on it updates every ~6 hours.
   (Prefer `*.pages.dev`? Create a free Cloudflare Pages project pointing at the `site` folder. Not needed.)
8. Check the run log: each account prints `ok` or `FAILED: reason`. The site's "Last updated" footer shows the last run.

## Adding accounts
Add a line under `instagram:` (or `tiktok:`) in `config.yaml`, e.g. `- {handle: new_club, category: sports, name: "New Club", acronym: "NC"}`, then commit and push.
A new account's first run reads its latest 50 posts; later runs read 10.

## Instagram blocks (read this!)
Instagram often blocks requests from GitHub's servers when not logged in. If the log shows `401`/`403`/`429`/"login required" for most accounts, use the fallback:
1. Create a throwaway Instagram account and, on your PC (with the venv active): `instaloader --login=THEUSERNAME`
2. Find the session file (Windows: `%LOCALAPPDATA%\Instaloader\session-THEUSERNAME`) and convert it:
   `[Convert]::ToBase64String([IO.File]::ReadAllBytes("PATH-TO-FILE"))` in PowerShell. Copy the long text.
3. GitHub repo > **Settings > Secrets and variables > Actions > New repository secret**: add `IG_USERNAME` and `IG_SESSION_B64` (the long text).
No code changes needed - the scraper uses them automatically. Risk: Instagram can lock automated accounts, and its terms restrict scraping; use at your own risk.

## Known limitations / first things to improve
- **Instagram/TikTok reliability** (above) is the biggest risk. The TikTok adapter is untested.
- Only the **first date** in a post becomes an event; posts listing several dates (a whole series) need a "one event per date" step.
- **Term dates**: the scraper for the uOttawa page is a best-effort guess I could not test; check `data/terms.json` or use `terms.override`.
- Club names/acronyms and categories are blank/guessed in `config.yaml` - fill them in.
- Translation of English-only/French-only events uses an unofficial free Google endpoint; if it fails the original text is shown.
- Only weekly/every-two-weeks recurrence; "Doors at 6, show at 7" picks the first time; "free pizza" is not read as a free event, but a prize like "win $500" can be misread as a price.
- Updates are matched to events by title/date similarity within the same club, so a vague follow-up may not match.
- No images of posts are stored (visual mode shows the club's profile picture, downloaded into `site/data/avatars`).
- OCR quality depends on the poster design; stylized fonts may fail.
