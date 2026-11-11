# How twowomenoneprison.com updates itself

**Method: a scheduled GitHub Action (free on a public repo).** `.github/workflows/refresh.yml` runs `build/build_site.py` every 3 hours, and also on demand (Actions tab → "Refresh site from feeds" → Run workflow).

It reads:
- the TWOP YouTube channel feed (full episodes and Shorts),
- Sabrena's Medium feed and Dawn's Substack feed (the same number of posts from each).

It rebuilds `index.html` and `episodes/*.html`, and commits only when something changed. GitHub Pages then republishes the site by itself.

Why this and not live loading in the visitor's browser:
- no outside "feed proxy" service to trust or pay for,
- works with JavaScript off,
- prints cleanly for people inside,
- search engines see every episode.

## Order
- Newest on top, Episode 1 at the bottom. A new upload lands on top by itself.
- Shorts sit under their episode, newest first.

## What's hand-written vs. automatic
- **Automatic:** new episodes, titles, dates, new Shorts, blog posts.
  - A Short that isn't hand-mapped goes under the newest episode published before it.
  - A new episode with no hand-written summary uses the first two sentences of its YouTube description. Write the description well and the site reads well.
- **Hand-written (`data/episodes.json`):** summaries, minutes, guest names, infographics, which Shorts belong where, the "Coming up" cards.
  - Edit it and push; the Action rebuilds.
- `data/archive.json` remembers every video and post ever seen. The YouTube feed only shows the newest 15, so older episodes never drop off.

## Co-owned: nothing promoted out (Dawn, 11 Nov)
TWOP belongs to both hosts, so it never promotes either host's other properties.
- Each host card has exactly one personal link, the same weight: Sabrena's Medium blog and Dawn's Substack.
- "From our blogs" shows the same number of posts from each host.
- No links to debrantes.com, thehippiediva.com, Homesteader Labs, FloofieButts or the kids' site.
- Other sites may link TO TWOP (one way).

## Notes
- GitHub pauses scheduled Actions on a repo with no activity for 60 days. The bot's own commits count as activity while episodes keep coming. If it ever pauses, click "Enable workflow" in the Actions tab.
