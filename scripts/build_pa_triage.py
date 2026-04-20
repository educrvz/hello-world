"""Build an HTML triage view for PA hidden rows using pa_regeocode_candidates.json.

Reads:
  - build/master_geocoded_patched_v1.csv    (current state of PA rows)
  - build/pa_regeocode_candidates.json      (best candidate from fresh geocode pass)

Writes:
  - build/pa_triage.html  (open in browser to review + export decisions)

The exported decisions CSV is compatible with scripts/apply_manual_triage.py.
"""

import csv
import html
import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "master_geocoded_patched_v1.csv"
CANDS = ROOT / "build" / "pa_regeocode_candidates.json"
OUT = ROOT / "build" / "pa_triage.html"

# Hand-graded confidence per row based on the regeocode pass results.
GRADES = {
    "PA_0067": ("high", "Same pin as old — hidden only because FA says 'Eldorado do Carajás' vs source 'Eldorado dos Carajás'."),
    "PA_0118": ("high", "Same pin as old — hidden only because FA says 'Piçarra' vs source 'Piçarras'."),
    "PA_0071": ("high", "ROOFTOP match on R. Tiradentes, matches source address."),
    "PA_0054": ("medium", "Source says 'Fernando Guillhom'; Google has Av. Fernando Guihon in Cap. Poço — likely the same street with spelling drift."),
    "PA_0076": ("medium", "Google returns a ROOFTOP match on Rua Tancredo Neves, but source says Rua Ulisses Guimarães. Worth eyeballing."),
    "PA_0171": ("medium", "Only a GEOMETRIC_CENTER match on Tv. Costa e Silva; source says Rua da Piçarreira."),
    "PA_0007": ("low", "All 5 query variants returned only Almeirim city centroid — Google doesn't know this hospital. Manual CNES lookup needed."),
    "PA_0029": ("low", "Best match is the São Joaquim district of Baião, not the hospital itself."),
    "PA_0055": ("low", "Google found a 'Almir Gabriel' road in Marituba (wrong city). 'Governador Almir Gabriel' is a common name."),
}

GRADE_ORDER = {"high": 0, "medium": 1, "low": 2}


def maps_pin(lat, lng):
    return f"https://www.google.com/maps?q={lat},{lng}" if lat and lng else ""


def maps_search(query):
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def load():
    with MASTER.open() as f:
        master = {r["row_id"]: r for r in csv.DictReader(f)}
    cands = {c["row_id"]: c for c in json.loads(CANDS.read_text())}
    rows = []
    for row_id in GRADES:
        m = master[row_id]
        c = cands.get(row_id, {})
        grade, rationale = GRADES[row_id]
        rows.append({
            "row_id": row_id,
            "uf": m["source_state_abbr"],
            "name": m["health_unit_name"],
            "muni": m["municipality"],
            "address": m["address"],
            "cnes": m["cnes"],
            "policy": m["publish_policy"],
            "grade": grade,
            "rationale": rationale,
            "old_lat": m["lat"],
            "old_lng": m["lng"],
            "old_fa": m["formatted_address"],
            "old_loc_type": m["location_type"],
            "best_lat": str(c.get("best_lat", "")),
            "best_lng": str(c.get("best_lng", "")),
            "best_fa": c.get("best_fa", ""),
            "best_loc_type": c.get("best_location_type", ""),
            "best_place_id": c.get("best_place_id", ""),
            "best_query_label": c.get("best_query_label", ""),
        })
    rows.sort(key=lambda r: (GRADE_ORDER[r["grade"]], r["row_id"]))
    return rows


def render_card(r):
    search_name = f"{r['name']} {r['muni']} {r['uf']} Brasil"
    search_addr = f"{r['address']} {r['muni']} {r['uf']} Brasil" if r["address"] else search_name
    grade_class = {"high": "grade-high", "medium": "grade-med", "low": "grade-low"}[r["grade"]]

    best_block = f"""
      <div class="pin best">
        <div class="pin-label">PROPOSED PIN <span class="muted">({html.escape(r['best_query_label'] or '—')})</span></div>
        <div class="fa">{html.escape(r['best_fa'] or '—')}</div>
        <div class="meta">{html.escape(r['best_loc_type'] or '?')}</div>
        <div class="meta mono">{html.escape(r['best_lat'])}, {html.escape(r['best_lng'])}</div>
        <a href="{maps_pin(r['best_lat'], r['best_lng'])}" target="_blank" rel="noopener">Open pin ↗</a>
      </div>
    """ if r["best_lat"] else '<div class="pin best empty">No candidate</div>'

    return f"""
    <article class="card" data-row-id="{html.escape(r['row_id'])}" data-grade="{r['grade']}" data-policy="{html.escape(r['policy'])}">
      <header>
        <span class="row-id">{html.escape(r['row_id'])}</span>
        <span class="uf">{html.escape(r['uf'])}</span>
        <span class="name">{html.escape(r['name'])}</span>
        <span class="muni">{html.escape(r['muni'])}</span>
        <span class="policy">{html.escape(r['policy'])}</span>
        <span class="grade {grade_class}">{r['grade']}</span>
      </header>
      <div class="rationale">{html.escape(r['rationale'])}</div>
      <div class="source">
        <div><strong>Source address:</strong> {html.escape(r['address'] or '—')}</div>
        <div><strong>CNES:</strong> {html.escape(r['cnes'] or '—')} ·
          <a href="{maps_search(search_name)}" target="_blank" rel="noopener">Search name+muni ↗</a> ·
          <a href="{maps_search(search_addr)}" target="_blank" rel="noopener">Search address ↗</a> ·
          <a href="https://cnes.datasus.gov.br/pages/estabelecimentos/consulta.jsp?search={html.escape(r['cnes'])}" target="_blank" rel="noopener">CNES DATASUS ↗</a>
        </div>
      </div>
      <div class="pins">
        <div class="pin old">
          <div class="pin-label">CURRENT (hidden) PIN</div>
          <div class="fa">{html.escape(r['old_fa'] or '—')}</div>
          <div class="meta">{html.escape(r['old_loc_type'] or '?')}</div>
          <div class="meta mono">{html.escape(r['old_lat'])}, {html.escape(r['old_lng'])}</div>
          <a href="{maps_pin(r['old_lat'], r['old_lng'])}" target="_blank" rel="noopener">Open pin ↗</a>
        </div>
        {best_block}
      </div>
      <div class="decision">
        <label><input type="radio" name="d-{html.escape(r['row_id'])}" value="accept_best"> Accept proposed</label>
        <label><input type="radio" name="d-{html.escape(r['row_id'])}" value="keep_hidden"> Keep hidden</label>
        <label><input type="radio" name="d-{html.escape(r['row_id'])}" value="manual"> Manual fix</label>
        <input type="text" class="note" name="n-{html.escape(r['row_id'])}" placeholder="notes or lat,lng for manual fix" />
      </div>
    </article>
    """


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>PA hidden rows triage</title>
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
  .grade-high {{ background:rgba(47,179,68,.15); color:var(--good); border:1px solid var(--good) }}
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
  <h1>PA hidden rows triage — <span id="total-n">{total}</span> rows</h1>
  <div class="filters">
    <label>Confidence
      <select id="f-grade">
        <option value="">all</option>
        <option value="high">high (start here)</option>
        <option value="medium">medium</option>
        <option value="low">low</option>
      </select>
    </label>
    <label>Policy
      <select id="f-policy">
        <option value="">all</option>
        <option value="hide_muni_mismatch">hide_muni_mismatch</option>
        <option value="hide_state_only">hide_state_only</option>
      </select>
    </label>
    <label><input type="checkbox" id="f-hide-decided"> hide decided</label>
    <button class="ghost" id="select-all-high">Accept all 🟢 high</button>
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
const STORAGE_KEY = "pa-triage-decisions-v1";
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
  const hd = document.getElementById("f-hide-decided").checked;
  let visible = 0, decidedVisible = 0, decidedTotal = 0;
  document.querySelectorAll(".card").forEach(card => {{
    const isDecided = card.classList.contains("decided");
    if (isDecided) decidedTotal++;
    const match = (!fg || card.dataset.grade === fg) &&
                  (!fp || card.dataset.policy === fp) &&
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

["f-grade", "f-policy", "f-hide-decided"].forEach(id =>
  document.getElementById(id).addEventListener("change", refreshCounters));

document.getElementById("select-all-high").addEventListener("click", () => {{
  document.querySelectorAll('.card[data-grade="high"]').forEach(card => {{
    const id = card.dataset.rowId;
    const radio = card.querySelector(`input[name="d-${{id}}"][value="accept_best"]`);
    if (radio && !radio.checked) {{
      radio.checked = true;
      saved[id] = Object.assign(saved[id] || {{}}, {{ decision: "accept_best" }});
      card.classList.add("decided");
    }}
  }});
  localStorage.setItem(STORAGE_KEY, JSON.stringify(saved));
  refreshCounters();
}});

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
    rows.push([id, card.dataset.uf || "PA",
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
  a.download = "pa_triage_decisions.csv";
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


def main():
    rows = load()
    cards = "\n".join(render_card(r) for r in rows)
    baked = {r["row_id"]: {k: r[k] for k in ["best_lat", "best_lng", "best_fa", "best_place_id", "best_loc_type"]}
             for r in rows}
    OUT.write_text(TEMPLATE.format(total=len(rows), cards=cards, baked=json.dumps(baked, ensure_ascii=False)))
    print(f"Wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
