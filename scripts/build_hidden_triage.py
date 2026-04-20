"""Generalized HTML triage view for hidden hospital rows.

Reads a candidates JSON (default: build/places_candidates.json) whose schema
matches scripts/places_lookup_hidden.py output — same keys as
pa_regeocode_candidates.json plus `grade`, `grade_rationale`, `best_types`,
`distance_km`.

Filters out HIGH grade (already auto-applied). Writes a single-file HTML
with side-by-side old/new pins, confidence pills, Google Maps + CNES DATASUS
links, decision radios, notes field, CSV export.

Usage:
  python3 scripts/build_hidden_triage.py
  python3 scripts/build_hidden_triage.py --candidates build/places_candidates.json \
    --output build/hidden_triage.html --ufs MG,PR,BA
"""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "master_geocoded_patched_v1.csv"

GRADE_ORDER = {"medium": 0, "low": 1}


def maps_pin(lat, lng):
    return f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else ""


def maps_search(q):
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(q)}"


def load_master():
    with MASTER.open() as f:
        return {r["row_id"]: r for r in csv.DictReader(f)}


def load_candidates(path: Path, ufs: set[str] | None) -> list[dict]:
    data = json.loads(path.read_text())
    out = []
    for c in data:
        if c.get("grade") == "high":
            continue
        if ufs and c.get("uf") not in ufs:
            continue
        out.append(c)
    out.sort(key=lambda c: (GRADE_ORDER.get(c.get("grade", ""), 9),
                            c.get("uf", ""), c.get("row_id", "")))
    return out


def render_card(c: dict, master: dict) -> str:
    m = master.get(c["row_id"], {})
    name = c.get("name") or m.get("health_unit_name", "")
    muni = c.get("municipality") or m.get("municipality", "")
    uf = c.get("uf") or m.get("source_state_abbr", "")
    address = m.get("address", "")
    cnes = m.get("cnes", "")
    policy = m.get("publish_policy", "")
    grade = c.get("grade", "low")
    rationale = c.get("grade_rationale", "")

    search_name = f"{name} {muni} {uf} Brasil"
    search_addr = f"{address} {muni} {uf} Brasil" if address else search_name

    grade_class = {"medium": "grade-med", "low": "grade-low"}.get(grade, "grade-low")
    has_best = bool(c.get("best_lat") and c.get("best_lng"))
    dist = c.get("distance_km")
    dist_s = f"{dist:.1f} km" if isinstance(dist, (int, float)) else "—"
    types = ", ".join(c.get("best_types") or []) or "—"
    prechecked_best = ' checked' if grade == "medium" else ''

    best_block = f"""
      <div class="pin best">
        <div class="pin-label">PROPOSED PIN
          <span class="muted">({html.escape(c.get('best_query_label','') or '—')})</span></div>
        <div class="fa">{html.escape(c.get('best_fa','') or '—')}</div>
        <div class="meta">{html.escape(c.get('best_location_type','') or '?')} · types: {html.escape(types)}</div>
        <div class="meta mono">{html.escape(c.get('best_lat',''))}, {html.escape(c.get('best_lng',''))}  ·  {html.escape(dist_s)}</div>
        <a href="{maps_pin(c.get('best_lat',''), c.get('best_lng',''))}" target="_blank" rel="noopener">Open pin ↗</a>
      </div>
    """ if has_best else '<div class="pin best empty">No Places candidate</div>'

    return f"""
    <article class="card" data-row-id="{html.escape(c['row_id'])}" data-grade="{grade}" data-policy="{html.escape(policy)}" data-uf="{html.escape(uf)}">
      <header>
        <span class="row-id">{html.escape(c['row_id'])}</span>
        <span class="uf">{html.escape(uf)}</span>
        <span class="name">{html.escape(name)}</span>
        <span class="muni">{html.escape(muni)}</span>
        <span class="policy">{html.escape(policy)}</span>
        <span class="grade {grade_class}">{grade}</span>
      </header>
      <div class="rationale">{html.escape(rationale)}</div>
      <div class="source">
        <div><strong>Source address:</strong> {html.escape(address or '—')}</div>
        <div><strong>CNES:</strong> {html.escape(cnes or '—')} ·
          <a href="{maps_search(search_name)}" target="_blank" rel="noopener">Search name+muni ↗</a> ·
          <a href="{maps_search(search_addr)}" target="_blank" rel="noopener">Search address ↗</a> ·
          <a href="https://cnes.datasus.gov.br/pages/estabelecimentos/consulta.jsp?search={html.escape(cnes)}" target="_blank" rel="noopener">CNES DATASUS ↗</a>
        </div>
      </div>
      <div class="pins">
        <div class="pin old">
          <div class="pin-label">CURRENT (hidden) PIN</div>
          <div class="fa">{html.escape(c.get('old_fa','') or '—')}</div>
          <div class="meta mono">{html.escape(c.get('old_lat',''))}, {html.escape(c.get('old_lng',''))}</div>
          <a href="{maps_pin(c.get('old_lat',''), c.get('old_lng',''))}" target="_blank" rel="noopener">Open pin ↗</a>
        </div>
        {best_block}
      </div>
      <div class="decision">
        <label><input type="radio" name="d-{html.escape(c['row_id'])}" value="accept_best"{prechecked_best}> Accept proposed</label>
        <label><input type="radio" name="d-{html.escape(c['row_id'])}" value="keep_hidden"> Keep hidden</label>
        <label><input type="radio" name="d-{html.escape(c['row_id'])}" value="manual"> Manual fix</label>
        <input type="text" class="note" name="n-{html.escape(c['row_id'])}" placeholder="notes or lat,lng for manual fix" />
      </div>
    </article>
    """


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{ --bg:#0f1115; --fg:#e7e9ee; --muted:#8b93a7; --line:#242836; --accent:#6aa8ff;
          --good:#2fb344; --bad:#e55353; --warn:#f2a33d; --meh:#7a8599; }}
  * {{ box-sizing:border-box }}
  body {{ background:var(--bg); color:var(--fg); font:14px/1.45 -apple-system,system-ui,Segoe UI,sans-serif;
         margin:0; padding:0 20px 120px }}
  header.page {{ position:sticky; top:0; background:var(--bg); padding:14px 0; z-index:10;
                 border-bottom:1px solid var(--line) }}
  header.page h1 {{ margin:0 0 6px; font-size:16px }}
  .filters {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; font-size:13px }}
  .filters select {{ background:#1a1e28; color:var(--fg); border:1px solid var(--line);
                     border-radius:6px; padding:4px 8px }}
  .counter {{ margin-left:auto; color:var(--muted) }}
  .card {{ border:1px solid var(--line); border-radius:10px; margin:14px 0; padding:12px 14px;
           background:#151925 }}
  .card header {{ display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; margin-bottom:6px }}
  .row-id {{ font-family:ui-monospace,monospace; color:var(--muted); font-size:12px }}
  .uf {{ background:var(--line); padding:1px 6px; border-radius:4px; font-size:11px }}
  .name {{ font-weight:600 }}
  .muni {{ color:var(--muted) }}
  .policy {{ color:var(--muted); font-family:ui-monospace,monospace; font-size:11px }}
  .grade {{ margin-left:auto; padding:2px 10px; border-radius:999px; font-size:11px; text-transform:uppercase;
            font-weight:700; letter-spacing:.05em }}
  .grade-med  {{ background:rgba(242,163,61,.15); color:var(--warn); border:1px solid var(--warn) }}
  .grade-low  {{ background:rgba(229,83,83,.15); color:var(--bad); border:1px solid var(--bad) }}
  .rationale {{ color:var(--muted); font-size:12px; margin-bottom:8px; font-style:italic }}
  .source {{ font-size:13px; color:#cfd3dd; margin-bottom:10px }}
  .source a {{ color:var(--accent); text-decoration:none }}
  .source a:hover {{ text-decoration:underline }}
  .pins {{ display:grid; grid-template-columns:1fr 1fr; gap:10px }}
  .pin {{ background:#10131b; border:1px solid var(--line); border-radius:8px; padding:10px }}
  .pin.old {{ border-left:3px solid var(--bad) }}
  .pin.best {{ border-left:3px solid var(--good) }}
  .pin.best.empty {{ border-left:3px solid var(--meh); color:var(--muted); font-style:italic }}
  .pin-label {{ font-size:11px; color:var(--muted); letter-spacing:.08em; margin-bottom:4px }}
  .pin .fa {{ font-size:13px; margin-bottom:4px }}
  .pin .meta {{ font-size:11px; color:var(--muted) }}
  .pin .mono {{ font-family:ui-monospace,monospace }}
  .pin a {{ color:var(--accent); text-decoration:none; font-size:12px }}
  .pin a:hover {{ text-decoration:underline }}
  .muted {{ color:var(--muted) }}
  .decision {{ margin-top:10px; display:flex; gap:14px; align-items:center; flex-wrap:wrap;
               padding-top:8px; border-top:1px dashed var(--line) }}
  .decision label {{ cursor:pointer; user-select:none }}
  .decision .note {{ flex:1; min-width:260px; background:#10131b; border:1px solid var(--line);
                     color:var(--fg); border-radius:6px; padding:4px 8px;
                     font-family:ui-monospace,monospace; font-size:12px }}
  .card.decided {{ opacity:.55 }}
  .card.hidden-by-filter {{ display:none }}
  footer.bar {{ position:fixed; bottom:0; left:0; right:0; background:#0b0d13; border-top:1px solid var(--line);
                padding:12px 20px; display:flex; gap:12px; align-items:center }}
  button {{ background:var(--accent); color:#0b0d13; border:0; border-radius:6px; padding:8px 14px;
            font-weight:600; cursor:pointer }}
  button.ghost {{ background:transparent; color:var(--fg); border:1px solid var(--line) }}
</style>
</head>
<body>
<header class="page">
  <h1>{title} — <span id="total-n">{total}</span> rows</h1>
  <div class="filters">
    <label>Grade
      <select id="f-grade"><option value="">all</option><option value="medium">medium (pre-accepted)</option><option value="low">low</option></select>
    </label>
    <label>Policy
      <select id="f-policy"><option value="">all</option><option value="hide_muni_mismatch">hide_muni_mismatch</option><option value="hide_state_only">hide_state_only</option><option value="hide_external_review">hide_external_review</option></select>
    </label>
    <label>UF
      <select id="f-uf"><option value="">all</option>{uf_options}</select>
    </label>
    <label><input type="checkbox" id="f-hide-decided"> hide decided</label>
    <button class="ghost" id="commit-prechecks">Commit pre-checks for all visible medium</button>
    <span class="counter"><span id="decided-n">0</span>/<span id="visible-n">0</span> decided (visible)</span>
  </div>
</header>
<main id="cards">
{cards}
</main>
<footer class="bar">
  <button id="copy">Copy decisions CSV</button>
  <button id="download" class="ghost">Download CSV</button>
  <button id="reset" class="ghost">Reset saved decisions</button>
  <span class="counter"><span id="decided-total">0</span>/{total} decided total (auto-saved to this browser)</span>
</footer>
<script>
const STORAGE_KEY = {storage_key_json};
const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{{}}");

function applyDecision(card) {{
  const id = card.dataset.rowId;
  const d = saved[id] || {{}};
  if (d.decision) {{
    const radio = card.querySelector(`input[name="d-${{id}}"][value="${{d.decision}}"]`);
    if (radio) radio.checked = true;
    card.classList.add("decided");
  }}
  const note = card.querySelector(`input[name="n-${{id}}"]`);
  if (note && d.note) note.value = d.note;
}}

function refreshCounters() {{
  const fg = document.getElementById("f-grade").value;
  const fp = document.getElementById("f-policy").value;
  const fu = document.getElementById("f-uf").value;
  const hd = document.getElementById("f-hide-decided").checked;
  let visible = 0, decidedVisible = 0, decidedTotal = 0;
  document.querySelectorAll(".card").forEach(card => {{
    const isDecided = card.classList.contains("decided");
    if (isDecided) decidedTotal++;
    const match = (!fg || card.dataset.grade === fg) &&
                  (!fp || card.dataset.policy === fp) &&
                  (!fu || card.dataset.uf === fu) &&
                  (!hd || !isDecided);
    if (match) {{ card.classList.remove("hidden-by-filter"); visible++; if (isDecided) decidedVisible++; }}
    else {{ card.classList.add("hidden-by-filter"); }}
  }});
  document.getElementById("visible-n").textContent = visible;
  document.getElementById("decided-n").textContent = decidedVisible;
  document.getElementById("decided-total").textContent = decidedTotal;
}}

document.querySelectorAll(".card").forEach(card => {{
  applyDecision(card);
  const id = card.dataset.rowId;
  card.querySelectorAll(`input[type=radio][name="d-${{id}}"]`).forEach(r => {{
    r.addEventListener("change", () => {{
      saved[id] = Object.assign(saved[id] || {{}}, {{ decision: r.value }});
      localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
      card.classList.add("decided");
      refreshCounters();
    }});
  }});
  const note = card.querySelector(`input[name="n-${{id}}"]`);
  if (note) note.addEventListener("input", () => {{
    saved[id] = Object.assign(saved[id] || {{}}, {{ note: note.value }});
    localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  }});
}});

document.getElementById("commit-prechecks").addEventListener("click", () => {{
  let n = 0;
  document.querySelectorAll('.card:not(.hidden-by-filter)[data-grade="medium"]').forEach(card => {{
    const id = card.dataset.rowId;
    const radio = card.querySelector(`input[name="d-${{id}}"][value="accept_best"]`);
    if (radio && radio.checked && !saved[id]?.decision) {{
      saved[id] = Object.assign(saved[id] || {{}}, {{ decision: "accept_best" }});
      card.classList.add("decided");
      n++;
    }}
  }});
  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  refreshCounters();
  alert(`Committed ${{n}} pre-check(s) as decisions.`);
}});

["f-grade", "f-policy", "f-uf", "f-hide-decided"].forEach(id =>
  document.getElementById(id).addEventListener("change", refreshCounters));

const BAKED = {baked};

function buildCsv() {{
  const rows = [["row_id", "uf", "name", "municipality", "outcome", "decision",
                 "best_lat", "best_lng", "note",
                 "best_formatted_address", "best_place_id", "best_location_type"]];
  document.querySelectorAll(".card").forEach(card => {{
    const id = card.dataset.rowId;
    const d = saved[id];
    if (!d || !d.decision) return;
    const b = BAKED[id] || {{}};
    rows.push([id, card.dataset.uf,
               card.querySelector(".name").textContent,
               card.querySelector(".muni").textContent,
               card.dataset.grade, d.decision,
               b.best_lat || "", b.best_lng || "", (d.note || ""),
               b.best_fa || "", b.best_place_id || "", b.best_loc_type || ""]);
  }});
  return rows.map(r => r.map(c => {{
    c = String(c);
    return /[",\\n]/.test(c) ? `"${{c.replaceAll('"', '""')}}"` : c;
  }}).join(",")).join("\\n");
}}

document.getElementById("copy").addEventListener("click", async () => {{
  await navigator.clipboard.writeText(buildCsv());
  alert("Decisions CSV copied to clipboard.");
}});
document.getElementById("download").addEventListener("click", () => {{
  const blob = new Blob([buildCsv()], {{ type: "text/csv" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "hidden_triage_decisions.csv";
  a.click();
}});
document.getElementById("reset").addEventListener("click", () => {{
  if (!confirm("Clear all saved decisions in this browser?")) return;
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
}});

refreshCounters();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", default=str(ROOT / "build" / "places_candidates.json"))
    ap.add_argument("--output", default=str(ROOT / "build" / "hidden_triage.html"))
    ap.add_argument("--ufs", help="comma-separated UFs to include")
    ap.add_argument("--title", default="Hidden rows triage (Places rescue)")
    ap.add_argument("--storage-key", default="hidden-triage-decisions-v1")
    args = ap.parse_args()

    ufs = set(s.strip().upper() for s in args.ufs.split(",")) if args.ufs else None
    candidates = load_candidates(Path(args.candidates), ufs)
    master = load_master()

    uf_list = sorted({c.get("uf", "") for c in candidates if c.get("uf")})
    uf_options = "".join(f'<option value="{u}">{u}</option>' for u in uf_list)
    cards = "\n".join(render_card(c, master) for c in candidates)
    baked = {c["row_id"]: {k: c.get(k, "") for k in
                          ("best_lat", "best_lng", "best_fa", "best_place_id")} |
                          {"best_loc_type": c.get("best_location_type", "")}
             for c in candidates}

    html_out = TEMPLATE.format(
        title=html.escape(args.title),
        total=len(candidates),
        uf_options=uf_options,
        cards=cards,
        baked=json.dumps(baked, ensure_ascii=False),
        storage_key_json=json.dumps(args.storage_key),
    )
    Path(args.output).write_text(html_out)
    print(f"Wrote {args.output} ({len(candidates)} rows)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
