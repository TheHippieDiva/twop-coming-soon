#!/usr/bin/env python3
"""Two Women One Prison site builder. AUTO-FEED: run by .github/workflows/refresh.yml every 3 hours.
Reads the TWOP YouTube feed + both hosts' blog feeds, keeps everything ever seen in data/archive.json
(the YouTube feed only shows the newest 15), and rebuilds index.html + episodes/*.html.
Newest on top, Ep 1 at the bottom: a new upload lands on top by itself.
Hand-written extras (episode summaries, infographics, which Shorts belong to which episode) live in data/episodes.json.
Run locally: python3 build/build_site.py [site_root]   (no network = builds from the archive)
House rules: co-owned show, equal credit; it never promotes either host's other properties (one personal blog link each, same weight)."""
import html, json, os, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))
CHANNEL = "UCisP_TUOE8fXaQeg9WaAZ5A"
YT_FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL}"
BLOGS = [  # equal credit: same number of posts from each host
  dict(author="Sabrena", name="Sabrena on Medium", home="https://sabrena-morgan-missouri.medium.com", feed="https://sabrena-morgan-missouri.medium.com/feed"),
  dict(author="Dawn", name="Dawn on Substack", home="https://thehippiediva.substack.com", feed="https://thehippiediva.substack.com/feed"),
]
POSTS_EACH = 3
# TWOP is co-owned: it links OUT to nobody's other properties (Dawn 11 Nov). Other sites may link TO TWOP.
HOSTS = "with Sabrena Morgan &amp; Dawn de Brantes"
FOOT = "Our own experiences and opinions. Not legal advice. Adult topics and strong language. Take care of yourself."
UA = {"User-Agent": "Mozilla/5.0 (twowomenoneprison.com site builder)"}

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Archivo+Black&family=IBM+Plex+Mono:wght@500&family=Josefin+Sans:wght@400;600;700&display=swap" rel="stylesheet">')

CSS = r"""
:root{--bg:#fbf7f4;--card:#f4ede7;--ink:#2a2026;--head:#4f2445;--accent:#a85a1c;--muted:#6b5d63;--line:#e2d8d0;--onaccent:#fbf7f4;color-scheme:light}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#2b2b2b;--card:#353535;--ink:#eee6dc;--head:#eee6dc;--accent:#d49066;--muted:#c4bcb3;--line:#4a4a4a;--onaccent:#2b2b2b;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#2b2b2b;--card:#353535;--ink:#eee6dc;--head:#eee6dc;--accent:#d49066;--muted:#c4bcb3;--line:#4a4a4a;--onaccent:#2b2b2b;color-scheme:dark}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:18px/1.6 'Josefin Sans',system-ui,sans-serif;overflow-x:hidden}
img{max-width:100%;height:auto;display:block}
a{color:var(--accent);text-underline-offset:3px}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}
.skip{position:absolute;left:-999px}.skip:focus{left:16px;top:8px;background:var(--card);padding:10px;z-index:9}
header.top{border-bottom:1px solid var(--line)}
header.top .wrap{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:4px 16px;padding-top:6px;padding-bottom:6px}
.brand{font-family:'Archivo Black',Impact,sans-serif;font-size:19px;letter-spacing:.3px;color:var(--head);text-decoration:none;min-height:44px;display:flex;align-items:center}
.brand span{color:var(--accent)}
nav.top{display:flex;flex-wrap:wrap;gap:0 4px}
nav.top a{display:inline-flex;align-items:center;min-height:44px;padding:0 10px;text-decoration:none;font-weight:600;color:var(--ink)}
nav.top a:hover{color:var(--accent)}
h1,h2,h3{font-family:'Archivo Black',Impact,sans-serif;font-weight:400;color:var(--head);line-height:1.15;letter-spacing:.2px}
h1{font-size:clamp(28px,6vw,44px);margin:20px 0 8px}
h2{font-size:clamp(24px,4.5vw,32px);margin:44px 0 12px}
h3{font-size:21px;margin:0 0 6px}
.label{font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:13px;letter-spacing:.8px;text-transform:uppercase;color:var(--accent)}
.muted{color:var(--muted)}
.hero img{width:100%;border-radius:10px;margin-top:16px}
.hero .hosts{font-size:clamp(18px,3.4vw,22px);font-weight:600;margin:14px 0 0;color:var(--head)}
.lede{font-size:20px;max-width:46em}
.btns{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0 0}
.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:0 22px;border-radius:99px;font-weight:700;text-decoration:none;background:var(--accent);color:var(--onaccent)}
.btn.ghost{background:transparent;color:var(--accent);border:1.5px solid var(--accent)}
.vid{position:relative;padding-top:56.25%;border-radius:10px;overflow:hidden;background:#1d1b1c;margin:12px 0}
.vid iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.ep{display:grid;grid-template-columns:minmax(0,320px) minmax(0,1fr);gap:16px;margin:16px 0}
.ep .thumb{display:block;border-radius:8px;overflow:hidden;aspect-ratio:16/9;background:var(--line)}
.ep .thumb img{width:100%;height:100%;object-fit:cover}
.ep h3 a{color:var(--head);text-decoration:none}.ep h3 a:hover{color:var(--accent)}
.ep p{margin:6px 0}
.ep>*{min-width:0}
.ep h3 a,#newest h3 a{display:inline-block;min-height:44px;padding:4px 0}
.btnlink,footer a{display:inline-flex;align-items:center;min-height:44px}
.more{display:inline-flex;align-items:center;min-height:44px;font-weight:700}
.shorts{grid-column:1/-1}
.srow{display:flex;gap:10px;overflow-x:auto;padding:4px 0 10px;scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}
.srow a{flex:0 0 132px;scroll-snap-align:start;text-decoration:none;color:var(--ink);font-size:14px;line-height:1.3}
.srow .v{aspect-ratio:9/16;border-radius:8px;overflow:hidden;background:var(--line);margin-bottom:6px}
.srow .v img{width:100%;height:100%;object-fit:cover}
.note{border:1.5px dashed var(--accent);border-radius:10px;padding:10px 14px;color:var(--muted);margin:8px 0}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:16px}
.hostcard p{margin:6px 0 10px}
.links a{display:flex;align-items:center;min-height:44px;border-top:1px solid var(--line);text-decoration:none;font-weight:600}
.coming .card{display:flex;flex-direction:column}
.coming img{border-radius:8px;margin-top:10px;max-height:420px;object-fit:cover;object-position:top}
.infog{width:100%;max-width:min(100%,540px);margin:12px 0;border-radius:10px;border:1px solid var(--line)}
.print-url{display:none}
footer{border-top:1px solid var(--line);margin-top:56px;padding:20px 0 40px;color:var(--muted);font-size:16px}
footer .hosts{color:var(--head);font-weight:600}
.blog .item{border-top:1px solid var(--line);padding:10px 0}.blog .item a{font-weight:700;text-decoration:none;display:inline-block;min-height:44px;padding-top:8px}.blog .date{font-family:'IBM Plex Mono',monospace;font-size:13px;color:var(--muted)}
.crumbs{margin:16px 0 0}.crumbs a{display:inline-flex;align-items:center;min-height:44px}
@media (max-width:640px){.ep{grid-template-columns:minmax(0,1fr)}body{font-size:17px}.lede{font-size:18px}}
@media print{
 :root,:root[data-theme="dark"]{--bg:#fff;--card:#fff;--ink:#000;--head:#000;--accent:#000;--muted:#333;--line:#999}
 body{background:#fff;color:#000;font-size:12pt}
 .vid,nav.top,.btns,.btn,.srow,.skip,.more,.crumbs{display:none!important}
 .print-url{display:inline;font-family:'IBM Plex Mono',monospace;font-size:9pt;font-weight:400}
 .card{border:1px solid #999;break-inside:avoid}
 .ep{grid-template-columns:1fr}.ep .thumb{display:none}
 a{color:#000}
}
"""


def esc(s): return html.escape(s or "", quote=True)

def get(url, timeout=20):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r: return r.read()
    except Exception as e:
        print("feed skipped:", url, e); return None

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None

def is_short(vid, title):
    if "#shorts" in title.lower(): return True
    try:
        op = urllib.request.build_opener(NoRedirect)
        return op.open(urllib.request.Request(f"https://www.youtube.com/shorts/{vid}", headers=UA, method="HEAD"), timeout=15).status == 200
    except Exception: return False

def refresh(arc):
    raw = get(YT_FEED)
    if raw:
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "m": "http://search.yahoo.com/mrss/"}
        for en in ET.fromstring(raw).findall("a:entry", ns):
            vid = en.find("yt:videoId", ns).text; title = en.find("a:title", ns).text or ""
            d = en.find("m:group/m:description", ns)
            old = arc["videos"].get(vid, {})
            arc["videos"][vid] = dict(title=title, published=en.find("a:published", ns).text,
                                      short=old["short"] if "short" in old and old.get("published") else is_short(vid, title),
                                      desc=(d.text or "") if d is not None else "")
    for b in BLOGS:
        raw = get(b["feed"])
        if not raw: continue
        for it in ET.fromstring(raw).iter("item"):
            link = (it.findtext("link") or "").split("?")[0]
            try: pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(timezone.utc).isoformat()
            except Exception: continue
            arc["posts"][link] = dict(title=(it.findtext("title") or "").strip(), published=pub, author=b["author"])
    return arc

def nice(iso):
    try: return datetime.fromisoformat(iso).strftime("%b %-d").upper()
    except Exception: return ""

def auto_summary(desc):
    keep = [l.strip() for l in desc.splitlines() if l.strip() and not re.search(r"https?://|#|\d+:\d\d|^chapters|^content note|subscribe", l.strip(), re.I)]
    text = " ".join(keep)
    sents = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(sents[:2]).strip()
    return [out or "New episode. Watch it on YouTube."]

def clean_title(t): return re.sub(r"\s*\|\s*Two Women One Prison.*$", "", t).strip()

def build_eps(arc, cur):
    full = sorted(((v, i) for i, v in arc["videos"].items() if not v["short"] and v.get("published")), key=lambda x: x[0]["published"])
    eps = []
    for n, (v, vid) in enumerate(full, 1):
        c = cur["episodes"].get(vid, {})
        slug = c.get("slug") or f"ep{n}-" + re.sub(r"[^a-z0-9]+", "-", clean_title(v["title"]).lower()).strip("-")[:40]
        eps.append(dict(c, n=c.get("n", n), id=vid, slug=slug, title=clean_title(v["title"]), date=nice(v["published"]),
                        published=v["published"], summary=c.get("summary") or auto_summary(v.get("desc", "")), mins=c.get("mins", ""), shorts=[]))
    # Shorts: hand-mapped first, the rest go under the newest episode published before them
    mapped = {}
    for e in eps:
        for sid in cur["episodes"].get(e["id"], {}).get("shorts", []): mapped[sid] = e
    shorts = sorted(((v, i) for i, v in arc["videos"].items() if v["short"]), key=lambda x: x[0].get("published") or "")
    for v, sid in shorts:
        e = mapped.get(sid)
        if not e:
            before = [x for x in eps if x["published"] <= (v.get("published") or "")]
            e = before[-1] if before else None
        if e: e["shorts"].append((sid, re.sub(r"\s*#shorts\b", "", v["title"], flags=re.I).strip()))
    for e in eps: e["shorts"].reverse()          # newest Short first
    eps.reverse()                                # newest episode on top, Ep 1 at the bottom
    return eps

def posts_block(arc, root=""):
    cols = ""
    for b in BLOGS:
        ps = sorted((p | {"url": u} for u, p in arc["posts"].items() if p["author"] == b["author"]), key=lambda p: p["published"], reverse=True)[:POSTS_EACH]
        items = "".join(f'<div class="item"><div class="date">{nice(p["published"])}</div><a href="{esc(p["url"])}">{esc(p["title"])}</a></div>' for p in ps) or '<p class="muted">New posts show up here by themselves.</p>'
        cols += f'<div class="card blog"><h3>{esc(b["name"])}</h3>{items}<div class="links"><a href="{b["home"]}">Read more from {b["author"]}</a></div></div>'
    return f'<section id="blogs"><h2>From our blogs</h2><p class="muted">Newest on top. Updates by itself.</p><div class="grid2">{cols}</div></section>'

def page(title, desc, body, root=""):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="theme-color" content="#fbf7f4" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#2b2b2b" media="(prefers-color-scheme: dark)">
<meta property="og:title" content="Two Women One Prison"><meta property="og:description" content="{esc(desc)}"><meta property="og:image" content="https://twowomenoneprison.com/img/header.jpg">
<link rel="icon" href="{root}img/logo.jpg">
{FONTS}
<style>{CSS}</style></head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap"><a class="brand" href="{root}index.html">TWO WOMEN&nbsp;<span>ONE PRISON</span></a>
<nav class="top" aria-label="Main"><a href="{root}index.html#episodes">Episodes</a><a href="{root}index.html#coming">Coming up</a><a href="{root}index.html#blogs">Blogs</a><a href="{root}index.html#hosts">Hosts</a><a href="{root}commissary/index.html">Commissary lists</a></nav></div></header>
<main id="main" class="wrap">
{body}
</main>
<footer><div class="wrap"><p class="hosts">Two Women One Prison, {HOSTS}</p><p>{FOOT}</p>
<p><a href="https://www.youtube.com/@TwoWomenOnePrison">Two Women One Prison on YouTube</a></p><p class="label">Updated {UPDATED}</p></div></footer>
</body></html>
"""

def yt(id): return f"https://www.youtube.com/watch?v={id}"

def shorts_row(e):
    if not e["shorts"]:
        return f'<div class="shorts"><p class="note">{esc(e.get("shorts_note","More Shorts coming."))}</p></div>' if e.get("shorts_note") else ""
    items = "".join(f'<a href="https://www.youtube.com/shorts/{sid}"><div class="v"><img src="https://i.ytimg.com/vi/{sid}/hqdefault.jpg" alt="" loading="lazy" width="480" height="360"></div>{esc(t)}</a>' for sid,t in e["shorts"])
    return f'<div class="shorts"><div class="label">Shorts from this episode</div><div class="srow">{items}</div></div>'

def meta(e):
    bits = [b for b in (f"EP {e['n']}", e["date"].upper(), e["mins"]) if b]
    if e.get("guest"): bits.append("with " + e["guest"])
    return " · ".join(bits)

def ep_card(e, root=""):
    href = f"{root}episodes/{e['slug']}.html"
    return f"""<article class="card ep" id="{e['slug']}">
<a class="thumb" href="{href}" aria-label="{esc(e['title'])}"><img src="https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg" alt="" loading="lazy" width="320" height="180"></a>
<div><div class="label">{esc(meta(e))}</div>
<h3><a href="{href}">{esc(e['title'])}</a> <span class="print-url">{yt(e['id'])}</span></h3>
<p>{esc(e['summary'][0])}</p>
<a class="more" href="{href}">Watch + read more</a></div>
{shorts_row(e)}
</article>"""

def embed(e):
    if e.get("age_gate"):
        return f"""<a class="thumb" href="{yt(e['id'])}" style="display:block;border-radius:10px;overflow:hidden;margin:12px 0"><img src="https://i.ytimg.com/vi/{e['id']}/hqdefault.jpg" alt="Watch on YouTube" width="480" height="360" style="width:100%;aspect-ratio:16/9;object-fit:cover"></a>
<p class="note">YouTube marks this one for adults, so it plays on YouTube, not here. <a href="{yt(e['id'])}">Watch on YouTube</a>.</p>"""
    return f'<div class="vid"><iframe src="https://www.youtube-nocookie.com/embed/{e["id"]}" title="{esc(e["title"])}" loading="lazy" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen></iframe></div>'

def ep_page(e):
    paras = "".join(f"<p>{esc(p)}</p>" for p in e["summary"])
    inf = ""
    if e.get("infographic"):
        inf = f'<h2>The numbers</h2><img class="infog" src="../img/infographics/{e["infographic"]}" alt="Infographic for Episode {e["n"]}" loading="lazy">'
    recap = f'<p><a class="btnlink" href="{e["recap"]}">Weekly recap for this episode</a></p>' if e.get("recap") else ""
    sh = shorts_row(e)
    sh = f"<h2>Shorts</h2>{sh}" if sh else ""
    body = f"""<p class="crumbs"><a href="../index.html#episodes">All episodes</a></p>
<div class="label">{esc(meta(e))}</div>
<h1>{esc(e['title'])} <span class="print-url">{yt(e['id'])}</span></h1>
{embed(e)}
<div class="lede">{paras}</div>
<p><a class="btnlink" href="{yt(e['id'])}">Watch on YouTube</a></p>
{recap}
{sh}
{inf}"""
    return page(f"Ep {e['n']} · Two Women One Prison", e["summary"][0], body, root="../")

def host(name, handle_bio, links):
    la = "".join(f'<a href="{u}">{esc(t)}</a>' for t,u in links)
    return f'<div class="card hostcard"><h3>{name}</h3><p>{esc(handle_bio)}</p><div class="links">{la}</div></div>'

def index(EPS, COMING, arc):
    new = EPS[0]
    cards = "\n".join(ep_card(e) for e in EPS)
    coming = ""
    for c in COMING:
        t, d, inf = c["title"], c["text"], c.get("commissary_infographic")
        img = '<a href="commissary/index.html"><img src="commissary/TWOP_commissary-infographic_v1.png" alt="Infographic: prison pay stayed the same, commissary prices did not" loading="lazy"></a>' if inf else ""
        coming += f'<div class="card"><div class="label">Coming</div><h3>{esc(t)}</h3><p>{esc(d)}</p>{img}</div>'
    hosts = (host("Sabrena Morgan",
                  "Sabrena started blogging from inside a federal prison and came home writing the way she talks: no sugar coating, no victim mentality, no waiting for anybody's validation. Years out now, she lives life on her own terms, and still can't leave a room without saying “when I was in prison.”",
                  [("Sabrena's blog on Medium","https://sabrena-morgan-missouri.medium.com")])
           + host("Dawn de Brantes",
                  "Dawn, The Hippie Diva, did her time and came home to rebuild from the dirt up. Today she's a homesteader, songwriter and self-taught AI nerd, making music about walking out of every kind of prison. She calls herself a Gen ex-con: suspicious, tinfoil hat and all, and done apologizing for it.",
                  [("Dawn's blog on Substack","https://thehippiediva.substack.com")]))
    body = f"""<section class="hero"><img src="img/header.jpg" alt="Two Women One Prison" width="1546" height="423">
<p class="hosts">{HOSTS}</p>
<h1>Real talk for adults going in, coming out, and the families who love them.</h1>
<p class="lede">We met serving time in federal prison. Pretrial, prison, halfway houses, home confinement, supervision: we've lived it, and we talk about it straight.</p>
<div class="btns"><a class="btn" href="https://www.youtube.com/@TwoWomenOnePrison?sub_confirmation=1">Subscribe on YouTube</a><a class="btn ghost" href="#episodes">All episodes</a></div>
</section>

<section id="newest"><h2>Newest episode</h2>
<div class="label">{esc(meta(new))}</div>
<h3><a href="episodes/{new['slug']}.html" style="color:var(--head);text-decoration:none">{esc(new['title'])}</a> <span class="print-url">{yt(new['id'])}</span></h3>
{embed(new)}
</section>

<section id="episodes"><h2>Every episode</h2>
<p class="muted">Newest on top, Episode 1 at the bottom. New episodes Wednesdays; each one lands here by itself, with its Shorts underneath.</p>
{cards}
<p><a class="more" href="https://www.youtube.com/@TwoWomenOnePrison/shorts">All Shorts on YouTube</a></p>
</section>

<section id="coming" class="coming"><h2>Coming up</h2><div class="grid2">{coming}</div></section>

{posts_block(arc)}

<section id="hosts"><h2>Your hosts</h2><div class="grid2">{hosts}</div></section>

<section id="resources"><h2>Free resources</h2>
<div class="card"><h3>Federal prison commissary lists</h3><p>Every BOP facility in one searchable list, with item prices for 46 of them. Free.</p>
<div class="links"><a href="commissary/index.html">Open the commissary lists</a></div></div>
</section>"""
    return page("Two Women One Prison",
                "Real talk about federal prison and coming home, with Sabrena Morgan and Dawn de Brantes. Every episode, Shorts and free resources.", body)


def main():
    global UPDATED
    cur = json.load(open(f"{ROOT}/data/episodes.json"))
    ap = f"{ROOT}/data/archive.json"
    arc = refresh(json.load(open(ap)))
    json.dump(arc, open(ap, "w"), indent=1, ensure_ascii=False, sort_keys=True)
    UPDATED = datetime.now(timezone.utc).strftime("%b %-d, %Y")
    eps = build_eps(arc, cur)
    os.makedirs(f"{ROOT}/episodes", exist_ok=True)
    open(f"{ROOT}/index.html", "w").write(index(eps, cur["coming"], arc))
    for e in eps: open(f"{ROOT}/episodes/{e['slug']}.html", "w").write(ep_page(e))
    print(f"built {len(eps)} episodes, {sum(len(e['shorts']) for e in eps)} Shorts, {len(arc['posts'])} posts")

UPDATED = ""
if __name__ == "__main__":
    main()
