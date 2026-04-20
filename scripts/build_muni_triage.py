"""Generate a single-file HTML triage view for hide_muni_mismatch rows.

Reads build/master_geocoded_patched_v1.csv (for the 99 currently hidden rows)
and build/muni_mismatch_repair_best_attempts.csv (for repair candidates).
Writes build/muni_mismatch_triage.html — open in a browser, accept/reject
each row's "best" candidate, export decisions as CSV.
"""

import csv
import html
import json
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "build" / "master_geocoded_patched_v1.csv"
REPAIRS = ROOT / "build" / "muni_mismatch_repair_best_attempts.csv"
OUT = ROOT / "build" / "muni_mismatch_triage.html"

OUTCOME_ORDER = {
    "improved_but_still_review": 0,
    "improved_confidently": 1,
    "unchanged_bad": 2,
    "inconclusive": 3,
    "": 4,
}


def maps_pin(lat: str, lng: str) -> str:
    if not lat or not lng:
        return ""
    return f"https://www.google.com/maps?q={lat},{lng}"


def maps_search(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def load_rows():
    with MASTER.open() as f:
        master = {r["row_id"]: r for r in csv.DictReader(f)
                  if r["publish_policy"] == "hide_muni_mismatch"}
    with REPAIRS.open() as f:
        repair = {r["row_id"]: r for r in csv.DictReader(f)}

    merged = []
    for row_id, m in master.items():
        r = repair.get(row_id, {})
        merged.append({
            "row_id": row_id,
            "uf": m.get("source_state_abbr", ""),
            "name": m.get("health_unit_name", ""),
            "muni": m.get("municipality", ""),
            "address": m.get("address", ""),
            "cnes": m.get("cnes", ""),
            "old_fa": r.get("old_formatted_address") or m.get("formatted_address", ""),
            "old_lat": r.get("old_lat") or m.get("lat", ""),
            "old_lng": r.get("old_lng") or m.get("lng", ""),
            "old_score": r.get("old_score", ""),
            "best_fa": r.get("best_formatted_address", ""),
            "best_lat": r.get("best_lat", ""),
            "best_lng": r.get("best_lng", ""),
            "best_query": r.get("best_candidate_query", ""),
            "best_pattern": r.get("best_candidate_pattern", ""),
            "best_score": r.get("best_candidate_score", ""),
            "score_delta": r.get("score_delta", ""),
            "best_location_type": r.get("best_location_type", ""),
            "outcome": r.get("repair_outcome", ""),
            "reasons": r.get("best_candidate_reasons", ""),
        })
    merged.sort(key=lambda x: (OUTCOME_ORDER.get(x["outcome"], 9), x["uf"], x["row_id"]))
    return merged


def render_card(r: dict) -> str:
    search_q = f"{r['name']} {r['muni']} {r['uf']} Brasil"
    src_addr_q = f"{r['address']} {r['muni']} {r['uf']} Brasil" if r["address"] else search_q

    outcome = r["outcome"] or "no_repair_attempt"
    outcome_class = {
        "improved_but_still_review": "outcome-review",
        "improved_confidently": "outcome-good",
        "unchanged_bad": "outcome-bad",
        "inconclusive": "outcome-meh",
    }.get(outcome, "outcome-meh")

    has_best = bool(r["best_lat"] and r["best_lng"])
    best_block = (
        f"""
        <div class="pin best">
          <div class="pin-label">BEST CANDIDATE <span class="muted">({html.escape(r['best_pattern'] or '—')})</span></div>
          <div class="fa">{html.escape(r['best_fa'] or '—')}</div>
          <div class="meta">score {html.escape(r['best_score'] or '?')}
               (Δ {html.escape(r['score_delta'] or '?')}) ·
               {html.escape(r['best_location_type'] or '?')}</div>
          <div class="meta mono">{html.escape(r['best_lat'])}, {html.escape(r['best_lng'])}</div>
          <a href="{maps_pin(r['best_lat'], r['best_lng'])}" target="_blank" rel="noopener">Open pin ↗</a>
          <div class="reasons">{html.escape(r['reasons'] or '')}</div>
        </div>
        """
        if has_best
        else '<div class="pin best empty">No repair candidate</div>'
    )

    return f"""
    <article class="card" data-row-id="{html.escape(r['row_id'])}" data-outcome="{html.escape(outcome)}" data-uf="{html.escape(r['uf'])}">
      <header>
        <span class="row-id">{html.escape(r['row_id'])}</span>
        <span class="uf">{html.escape(r['uf'])}</span>
        <span class="name">{html.escape(r['name'])}</span>
        <span class="muni">{html.escape(r['muni'])}</span>
        <span class="outcome {outcome_class}">{html.escape(outcome)}</span>
      </header>
      <div class="source">
        <div><strong>Source address:</strong> {html.escape(r['address'] or '—')}</div>
        <div><strong>CNES:</strong> {html.escape(r['cnes'] or '—')} ·
          <a href="{maps_search(search_q)}" target="_blank" rel="noopener">Search name+muni ↗</a> ·
          <a href="{maps_search(src_addr_q)}" target="_blank" rel="noopener">Search address ↗</a> ·
          <a href="https://cnes.datasus.gov.br/pages/estabelecimentos/consulta.jsp?search={html.escape(r['cnes'])}" target="_blank" rel="noopener">CNES DATASUS ↗</a>
        </div>
      </div>
      <div class="pins">
        <div class="pin old">
          <div class="pin-label">CURRENT (hidden) PIN</div>
          <div class="fa">{html.escape(r['old_fa'] or '—')}</div>
          <div class="meta">score {html.escape(r['old_score'] or '?')}</div>
          <div class="meta mono">{html.escape(r['old_lat'])}, {html.escape(r['old_lng'])}</div>
          <a href="{maps_pin(r['old_lat'], r['old_lng'])}" target="_blank" rel="noopener">Open pin ↗</a>
        </div>
        {best_block}
      </div>
      <div class="decision">
        <label><input type="radio" name="d-{html.escape(r['row_id'])}" value="accept_best"> Accept best</label>
        <label><input type="radio" name="d-{html.escape(r['row_id'])}" value="keep_hidden"> Keep hidden</label>
        <label><input type="radio" name="d-{html.escape(r['row_id'])}" value="manual"> Needs manual fix</label>
        <input type="text" class="note" name="n-{html.escape(r['row_id'])}" placeholder="notes (optional) — paste corrected lat,lng here for manual fixes" />
      </div>
    </article>
    """


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>hide_muni_mismatch triage</title>
<style>
  :root {{ --bg:#0f1115; --fg:#e7e9ee; --muted:#8b93a7; --line:#242836; --accent:#6aa8ff;
          --good:#2fb344; --bad:#e55353; --review:#f2a33d; --meh:#7a8599; }}
  * {{ box-sizing: border-box }}
  body {{ background:var(--bg); color:var(--fg); font:14px/1.45 -apple-system,system-ui,Segoe UI,sans-serif;
         margin:0; padding:0 20px 120px }}
  header.page {{ position:sticky; top:0; background:var(--bg); padding:14px 0; z-index:10;
                 border-bottom:1px solid var(--line) }}
  header.page h1 {{ margin:0 0 6px; font-size:16px }}
  .filters {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; font-size:13px }}
  .filters select, .filters input {{ background:#1a1e28; color:var(--fg); border:1px solid var(--line);
    border-radius:6px; padding:4px 8px }}
  .counter {{ margin-left:auto; color:var(--muted) }}
  .card {{ border:1px solid var(--line); border-radius:10px; margin:14px 0; padding:12px 14px;
           background:#151925 }}
  .card header {{ display:flex; gap:10px; align-items:baseline; flex-wrap:wrap; margin-bottom:8px }}
  .row-id {{ font-family:ui-monospace,monospace; color:var(--muted); font-size:12px }}
  .uf {{ background:var(--line); padding:1px 6px; border-radius:4px; font-size:11px; letter-spacing:.05em }}
  .name {{ font-weight:600 }}
  .muni {{ color:var(--muted) }}
  .outcome {{ margin-left:auto; padding:2px 8px; border-radius:999px; font-size:11px; text-transform:uppercase;
              letter-spacing:.05em }}
  .outcome-review {{ background:rgba(242,163,61,.15); color:var(--review); border:1px solid var(--review) }}
  .outcome-good {{ background:rgba(47,179,68,.15); color:var(--good); border:1px solid var(--good) }}
  .outcome-bad {{ background:rgba(229,83,83,.15); color:var(--bad); border:1px solid var(--bad) }}
  .outcome-meh {{ background:rgba(122,133,153,.15); color:var(--meh); border:1px solid var(--meh) }}
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
  .reasons {{ font-size:11px; color:var(--muted); margin-top:4px; font-style:italic }}
  .decision {{ margin-top:10px; display:flex; gap:14px; align-items:center; flex-wrap:wrap;
               padding-top:8px; border-top:1px dashed var(--line) }}
  .decision label {{ cursor:pointer; user-select:none }}
  .decision .note {{ flex:1; min-width:260px; background:#10131b; border:1px solid var(--line);
                     color:var(--fg); border-radius:6px; padding:4px 8px; font-family:ui-monospace,monospace; font-size:12px }}
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
  <h1>hide_muni_mismatch triage — <span id="total-n">{total}</span> rows</h1>
  <div class="filters">
    <label>Outcome
      <select id="f-outcome">
        <option value="">all</option>
        <option value="improved_but_still_review" selected>improved_but_still_review (start here)</option>
        <option value="unchanged_bad">unchanged_bad</option>
        <option value="improved_confidently">improved_confidently</option>
        <option value="inconclusive">inconclusive</option>
      </select>
    </label>
    <label>UF
      <select id="f-uf"><option value="">all</option>{uf_options}</select>
    </label>
    <label><input type="checkbox" id="f-hide-decided"> hide decided</label>
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
const STORAGE_KEY = "muni-triage-decisions-v1";
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
  const fOutcome = document.getElementById("f-outcome").value;
  const fUf = document.getElementById("f-uf").value;
  const hideDecided = document.getElementById("f-hide-decided").checked;
  let visible = 0, decidedVisible = 0, decidedTotal = 0;
  document.querySelectorAll(".card").forEach(card => {{
    const id = card.dataset.rowId;
    const isDecided = card.classList.contains("decided");
    if (isDecided) decidedTotal++;
    const matchOutcome = !fOutcome || card.dataset.outcome === fOutcome;
    const matchUf = !fUf || card.dataset.uf === fUf;
    const matchDecided = !hideDecided || !isDecided;
    if (matchOutcome && matchUf && matchDecided) {{
      card.classList.remove("hidden-by-filter");
      visible++;
      if (isDecided) decidedVisible++;
    }} else {{
      card.classList.add("hidden-by-filter");
    }}
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

["f-outcome", "f-uf", "f-hide-decided"].forEach(id =>
  document.getElementById(id).addEventListener("change", refreshCounters));

function buildCsv() {{
  const rows = [["row_id", "uf", "name", "municipality", "outcome", "decision",
                 "best_lat", "best_lng", "note"]];
  document.querySelectorAll(".card").forEach(card => {{
    const id = card.dataset.rowId;
    const d = saved[id];
    if (!d || !d.decision) return;
    const pin = card.querySelector(".pin.best .mono");
    const [lat, lng] = (pin ? pin.textContent : ",").split(",").map(s => s.trim());
    rows.push([id, card.dataset.uf,
               card.querySelector(".name").textContent,
               card.querySelector(".muni").textContent,
               card.dataset.outcome, d.decision,
               lat || "", lng || "", (d.note || "").replaceAll('"', '""')]);
  }});
  return rows.map(r => r.map(c => /[",\\n]/.test(c) ? `"${{c}}"` : c).join(",")).join("\\n");
}}

document.getElementById("copy").addEventListener("click", async () => {{
  await navigator.clipboard.writeText(buildCsv());
  alert("Decisions CSV copied to clipboard.");
}});
document.getElementById("download").addEventListener("click", () => {{
  const blob = new Blob([buildCsv()], {{ type: "text/csv" }});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "muni_mismatch_decisions.csv";
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
    rows = load_rows()
    ufs = sorted({r["uf"] for r in rows if r["uf"]})
    uf_options = "".join(f'<option value="{u}">{u}</option>' for u in ufs)
    cards = "\n".join(render_card(r) for r in rows)
    OUT.write_text(TEMPLATE.format(total=len(rows), uf_options=uf_options, cards=cards))
    print(f"Wrote {OUT} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
