#!/usr/bin/env python3
"""Generate the nWave work-progress dashboard (Artifact HTML) from the backlog SSOT.

Regenerate: `uv run python scripts/gen_status_dashboard.py` -> writes the HTML, then
publish it via the Artifact tool at the printed path (same URL redeploys). Data source:
docs/analysis/jira-mirror-backlog.csv (regenerate that first with
`uv run python scripts/backlog_to_jira_csv.py`). Epics are DERIVED thematically (the
backlog has no formal epic field yet); priority comes from the backlog ## section.
"""
import csv
import html
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CSV = REPO / "docs/analysis/jira-mirror-backlog.csv"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "docs/analysis/nwave-status.html"

# Derived thematic epics (first match wins; keyword on id+title lowercased).
EPICS = [
    ("Gates &amp; Feature-End", ["gate", "feature-end", "seal", "examine", "readiness", "commit-slice", "slice-commit", "oracle", "carpaccio"]),
    ("Wave Methodology", ["wave", "discuss", "design", "devops", "distill", "deliver", "discover", "diverge", "scorecard", "density", "ceremony"]),
    ("Dispatch &amp; Spine", ["dispatch", "spine", "agent", "crafter", "bare", "reviewer", "swarm", "hoist"]),
    ("Testing &amp; Quality", ["test", "-at-", "coverage", "mutation", "pbt", "corpus", "pollution", "runner", "-ats", "flaky"]),
    ("Acceleration &amp; Tooling", ["accel", "lever", "jira", "mirror", "dashboard", "scaffold", "docgen", "prompt", "token", "compaction", "friction"]),
    ("Language &amp; Runtime", ["language", "adapter", "runtime", "python", "target", "agnostic", "polyglot", "rust", "pyc"]),
    ("Adoption &amp; Product", ["adoption", "value", "product", "vision", "roadmap", "beta", "experimental", "publish", "release", "ferrari", "multiplier"]),
]

def epic_of(text):
    t = text.lower()
    for name, kws in EPICS:
        if any(k in t for k in kws):
            return name
    return "Other"

PRI_ORDER = {"Highest": 0, "High": 1, "Medium": 2, "Low": 3}
PRI_LABEL = {"Highest": "Critical", "High": "High", "Medium": "Medium", "Low": "Low"}

rows = list(csv.DictReader(open(CSV)))
items = []
for r in rows:
    st = (r.get("Status") or "").strip().lower()
    status = "done" if st in ("done", "completata", "completato") else ("prog" if ("cors" in st or "progress" in st) else "todo")
    fid = (r.get("Labels") or "").upper()
    title = r.get("Summary", "")
    items.append({
        "id": fid, "title": title, "desc": r.get("Description", ""),
        "pri": r.get("Priority", "Medium"), "prilabel": PRI_LABEL.get(r.get("Priority", "Medium"), "Medium"),
        "status": status, "epic": epic_of(fid + " " + title),
    })

todo = [i for i in items if i["status"] == "todo"]
todo.sort(key=lambda i: PRI_ORDER.get(i["pri"], 2))
n_crit = sum(1 for i in todo if i["pri"] == "Highest")

# epic -> count (todo only), ordered by declared epic order then Other
epic_names = [e[0] for e in EPICS] + ["Other"]
epic_counts = {e: sum(1 for i in todo if i["epic"] == e) for e in epic_names}
epic_names = [e for e in epic_names if epic_counts[e] > 0]

session_done = [
    ("BRANCH-RED", "full-suite 5671/0 — vincolo ToC sbloccato"),
    ("F-DOCGEN-PHASE-VOCAB-COMPARATOR", "docgen alias-comparator — mode_registry 22/0"),
    ("F-RIGOR-MUTATION-KNOB", "mutmut deprecation cleanup — rigor_review 25/0"),
    ("F-DISTILL-WIRING", "presence-based gate-out assertion — distill_wiring 6/0"),
    ("F-JIRA-MIRROR-PRIORITY", "Jira priorità-da-sezione + rerank urgenza"),
    ("F-STATUS-DASHBOARD", "questo dashboard (epic + master/detail)"),
]

DATA = json.dumps(items, ensure_ascii=False)
ts = "2026-07-06"

HTML = f'''<title>nWave — Stato Avanzamento Lavori</title>
<style>
:root{{--bg:#f6f8f9;--panel:#fff;--panel2:#eef2f4;--ink:#16212b;--muted:#5c6b78;--line:#e3e9ed;--accent:#0ea5a4;--crit:#e5484d;--high:#e08704;--med:#4a7bd0;--low:#8b94a0;--done:#3a9e52;--prog:#e08704;}}
@media(prefers-color-scheme:dark){{:root{{--bg:#0e1519;--panel:#15201f;--panel2:#1b2827;--ink:#e7eef1;--muted:#93a3ac;--line:#233230;--accent:#2dd4bf;--crit:#ff6369;--high:#f5a623;--med:#6ba0f0;--low:#98a2ad;--done:#54c46a;--prog:#f5a623;}}}}
:root[data-theme="dark"]{{--bg:#0e1519;--panel:#15201f;--panel2:#1b2827;--ink:#e7eef1;--muted:#93a3ac;--line:#233230;--accent:#2dd4bf;--crit:#ff6369;--high:#f5a623;--med:#6ba0f0;--low:#98a2ad;--done:#54c46a;--prog:#f5a623;}}
:root[data-theme="light"]{{--bg:#f6f8f9;--panel:#fff;--panel2:#eef2f4;--ink:#16212b;--muted:#5c6b78;--line:#e3e9ed;--accent:#0ea5a4;--crit:#e5484d;--high:#e08704;--med:#4a7bd0;--low:#8b94a0;--done:#3a9e52;--prog:#e08704;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1300px;margin:0 auto;padding:26px 20px 60px}}
header.top{{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px 16px;border-bottom:2px solid var(--accent);padding-bottom:14px}}
h1{{font-size:25px;font-weight:750;margin:0;letter-spacing:-.02em}} h1 .w{{color:var(--accent)}}
.sub{{color:var(--muted);font-size:13px}} .stamp{{margin-left:auto;font:12px ui-monospace,monospace;color:var(--muted)}}
.headline{{background:linear-gradient(90deg,color-mix(in srgb,var(--done) 16%,transparent),transparent);border-left:3px solid var(--done);border-radius:6px;padding:11px 15px;margin:15px 0 22px;font-size:13.5px}} .headline b{{color:var(--done)}}
.summary{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:11px;margin-bottom:24px}}
.stat{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:13px 15px}}
.stat .n{{font:700 28px/1 ui-monospace,monospace;font-variant-numeric:tabular-nums;letter-spacing:-.02em}}
.stat .l{{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-top:5px}}
.stat.crit .n{{color:var(--crit)}} .stat.done .n{{color:var(--done)}} .stat.prog .n{{color:var(--prog)}} .stat.todo .n{{color:var(--accent)}}
.layout{{display:grid;grid-template-columns:1fr 400px;gap:20px;align-items:start}}
@media(max-width:920px){{.layout{{grid-template-columns:1fr}}}}
.epic{{background:var(--panel);border:1px solid var(--line);border-radius:12px;margin-bottom:16px;overflow:hidden}}
.epic > summary{{list-style:none;cursor:pointer;padding:13px 16px;display:flex;align-items:center;gap:10px;font-weight:650;font-size:14.5px;user-select:none}}
.epic > summary::-webkit-details-marker{{display:none}}
.epic > summary::before{{content:"▸";color:var(--muted);transition:transform .15s;font-size:12px}}
.epic[open] > summary::before{{transform:rotate(90deg)}}
.epic > summary .ec{{margin-left:auto;font:600 12px ui-monospace,monospace;background:var(--panel2);border-radius:20px;padding:2px 10px;color:var(--muted)}}
.epic .body{{padding:0 14px 12px}}
.card{{background:var(--bg);border:1px solid var(--line);border-left:3px solid var(--line);border-radius:7px;padding:8px 11px;margin-bottom:6px;cursor:pointer;transition:border-color .12s,background .12s}}
.card:hover{{background:var(--panel2)}} .card.sel{{border-color:var(--accent);background:var(--panel2)}}
.card .top{{display:flex;align-items:center;gap:7px}}
.card p{{margin:5px 0 0;font-size:13px;line-height:1.4}}
.card.p-critical{{border-left-color:var(--crit)}} .card.p-high{{border-left-color:var(--high)}} .card.p-medium{{border-left-color:var(--med)}} .card.p-low{{border-left-color:var(--low)}}
.pill{{font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:1px 6px;border-radius:4px;color:#fff;flex:none}}
.card.p-critical .pill{{background:var(--crit)}} .card.p-high .pill{{background:var(--high)}} .card.p-medium .pill{{background:var(--med)}} .card.p-low .pill{{background:var(--low)}}
.cid{{font:600 10px ui-monospace,monospace;color:var(--muted);word-break:break-all}}
.detail{{position:sticky;top:18px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;max-height:calc(100vh - 40px);overflow:auto}}
.detail .empty{{color:var(--muted);font-style:italic;font-size:13px}}
.detail h3{{margin:0 0 4px;font-size:16px;line-height:1.35;text-wrap:balance}}
.detail .meta{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0 14px}}
.detail .tag{{font:600 11px ui-monospace,monospace;padding:2px 8px;border-radius:5px;background:var(--panel2);color:var(--muted)}}
.detail .desc{{font-size:13.5px;line-height:1.6;color:var(--ink);white-space:pre-wrap}}
.detail .did{{font:600 11px ui-monospace,monospace;color:var(--accent);word-break:break-all;margin-bottom:8px}}
@media(max-width:920px){{.detail{{position:fixed;inset:auto 12px 12px 12px;top:auto;z-index:50;box-shadow:0 8px 40px rgba(0,0,0,.4);max-height:70vh;transform:translateY(120%);transition:transform .2s}} .detail.show{{transform:none}} .detail .close{{display:block}}}}
.detail .close{{display:none;position:absolute;top:12px;right:14px;background:none;border:none;color:var(--muted);font-size:22px;cursor:pointer}}
.foot{{margin-top:26px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:13px}}
</style>
<div class="wrap">
<header class="top"><h1>n<span class="w">W</span>ave — Stato Avanzamento</h1><span class="sub">backlog SSOT · click su un item per la descrizione</span><span class="stamp">aggiornato {ts}</span></header>
<div class="headline"><b>Oggi:</b> full-suite <b>5671/0</b> — branch-red azzerato, vincolo ToC sbloccato · Jira priorità+urgenza sistemato · analisi nWave-vs-Relay + 6 leve.</div>
<div class="summary">
  <div class="stat todo"><div class="n">{len(todo)}</div><div class="l">To Do</div></div>
  <div class="stat crit"><div class="n">{n_crit}</div><div class="l">Critical</div></div>
  <div class="stat done"><div class="n">{len(session_done)}</div><div class="l">Fatto oggi</div></div>
  <div class="stat"><div class="n">{len(epic_names)}</div><div class="l">Epic (temi)</div></div>
</div>
<div class="layout">
  <div class="cols" id="board"></div>
  <aside class="detail" id="detail"><button class="close" onclick="hideDetail()">×</button><p class="empty">Clicca un item a sinistra per vederne la descrizione completa.</p></aside>
</div>
<div class="foot">Generato da <code>scripts/gen_status_dashboard.py</code> ← <code>docs/product/backlog.md</code>. Epic = temi DERIVATI (il backlog non ha ancora un campo epic formale). To Do ordinato per urgenza.
<br>Fatto questa sessione: {" · ".join(html.escape(t) for _,t in session_done)}.</div>
</div>
<script>
const ITEMS={DATA};
const EPIC_ORDER={json.dumps(epic_names, ensure_ascii=False)};
const board=document.getElementById('board'), detail=document.getElementById('detail');
const todo=ITEMS.filter(i=>i.status==='todo').sort((a,b)=>({{Highest:0,High:1,Medium:2,Low:3}}[a.pri]||2)-({{Highest:0,High:1,Medium:2,Low:3}}[b.pri]||2));
for(const ep of EPIC_ORDER){{
  const its=todo.filter(i=>i.epic===ep); if(!its.length)continue;
  const d=document.createElement('details'); d.className='epic'; if(its.some(i=>i.pri==='Highest'))d.open=true;
  d.innerHTML=`<summary>${{ep}}<span class="ec">${{its.length}}</span></summary><div class="body"></div>`;
  const body=d.querySelector('.body');
  for(const it of its){{
    const c=document.createElement('div'); c.className='card p-'+it.prilabel.toLowerCase(); c.dataset.id=it.id;
    c.innerHTML=`<div class="top"><span class="pill">${{it.prilabel}}</span><span class="cid">${{it.id}}</span></div><p>${{esc(it.title)}}</p>`;
    c.onclick=()=>showDetail(it,c); body.appendChild(c);
  }}
  board.appendChild(d);
}}
let selCard=null;
function esc(s){{const e=document.createElement('div');e.textContent=s;return e.innerHTML;}}
function showDetail(it,card){{
  if(selCard)selCard.classList.remove('sel'); selCard=card; card.classList.add('sel');
  detail.innerHTML=`<button class="close" onclick="hideDetail()">×</button><div class="did">${{it.id}}</div><h3>${{esc(it.title)}}</h3><div class="meta"><span class="tag" style="color:var(--${{it.prilabel==='Critical'?'crit':it.prilabel.toLowerCase()}})">${{it.prilabel}}</span><span class="tag">${{it.epic}}</span><span class="tag">To Do</span></div><div class="desc">${{esc(it.desc||'(nessuna descrizione)')}}</div>`;
  detail.classList.add('show');
}}
function hideDetail(){{detail.classList.remove('show'); if(selCard){{selCard.classList.remove('sel');selCard=null;}}}}
</script>'''

OUT.write_text(HTML, encoding="utf-8")
print(f"wrote {OUT} ({{}}KB) | To Do {len(todo)} · crit {n_crit} · epics {len(epic_names)}: {{}}".format(len(HTML)//1024, ", ".join(f"{e}({epic_counts[e]})" for e in epic_names)))
