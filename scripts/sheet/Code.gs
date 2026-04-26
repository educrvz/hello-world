// SoroJá — Google Sheets companion script
//
// Managed copy lives at scripts/sheet/Code.gs in the sos-antiveneno repo.
// If you edit it in the Apps Script editor, also copy the change back to the
// repo so the next person can see the current version.
//
// One-time setup:
//   1) Open the sheet → Extensions → Apps Script → paste this file.
//   2) Project Settings → Script properties → add two entries:
//        GITHUB_TOKEN   — fine-grained PAT for educrvz/sos-antiveneno,
//                         Contents: Read and write. Expires in 1 year.
//        GITHUB_REPO    — educrvz/sos-antiveneno
//   3) Run setupSheet once (menu: SoroJá → Setup sheet) — creates the
//      Hospitals + Overrides tabs with headers and validation.
//   4) Run refreshHospitals (menu: SoroJá → Refresh hospitals list) — pulls
//      the current dataset into tab 1. Re-run after a dataset refresh.
//
// Daily workflow:
//   - Find the hospital in tab "Hospitals"; click "Current pin" / "Find
//     correct pin" to compare.
//   - Add a row in tab "Overrides" (cnes, corrected lat/lng and/or
//     corrected address and/or corrected note, reason). You may correct
//     coordinates, address, a warning note, or any combination — but
//     supplying only one of lat/lng (with the other blank) is an error.
//   - Menu: SoroJá → Publish overrides. Vercel deploys in ~1 minute.

const HOSPITALS_SHEET = 'Hospitals';
const OVERRIDES_SHEET = 'Overrides';
const COMMUNITY_NOTES_SHEET = 'Community Notes';
const OVERRIDES_PATH = 'data/location_overrides.json';
const COMMUNITY_NOTES_PATH = 'data/community_notes.json';
const RAW_HOSPITALS_URL =
  'https://raw.githubusercontent.com/educrvz/sos-antiveneno/main/hospitals.json';

const HOSPITAL_HEADERS = [
  'cnes', 'hospital_name', 'state', 'city', 'address',
  'lat', 'lng', 'geocode_tier', 'current_pin', 'search_address',
  'override_status',
];

const OVERRIDE_HEADERS = [
  'cnes', 'hospital_name (ref)', 'corrected_lat', 'corrected_lng',
  'corrected_address', 'corrected_note', 'reason', 'verified_on',
  'status', 'published_at',
];
// Column indices (1-based) for fields the script writes back to the sheet.
const OVERRIDE_COL_STATUS = 9;
const OVERRIDE_COL_PUBLISHED_AT = 10;

// Community notes tab — additive, dated relatos. One row per note;
// multiple rows for the same CNES become an array of notes on the
// hospital record. public_summary is maintainer-authored canned text
// (no raw user reports). See docs/community-reports-plan.md.
const COMMUNITY_NOTE_HEADERS = [
  'cnes', 'hospital_name (ref)', 'category', 'reported_at',
  'public_summary', 'expires_at', 'status', 'published_at',
];
const COMMUNITY_NOTE_COL_STATUS = 7;
const COMMUNITY_NOTE_COL_PUBLISHED_AT = 8;
const COMMUNITY_NOTE_CATEGORIES = ['contact_fix', 'pin_fix', 'closed', 'wrong_unit', 'other'];
const COMMUNITY_NOTE_SUMMARY_MAX = 280;

// Brazil bounding box — rejects obviously wrong paste values.
const LAT_MIN = -34, LAT_MAX = 6;
const LNG_MIN = -74, LNG_MAX = -33;


function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('SoroJá')
    .addItem('Publish overrides', 'publishOverrides')
    .addItem('Publicar relatos da comunidade', 'publishCommunityNotes')
    .addItem('Refresh hospitals list', 'refreshHospitals')
    .addSeparator()
    .addItem('Setup sheet (first time only)', 'setupSheet')
    .addToUi();
}


// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

function setupSheet() {
  const ss = SpreadsheetApp.getActive();

  let hosp = ss.getSheetByName(HOSPITALS_SHEET);
  if (!hosp) hosp = ss.insertSheet(HOSPITALS_SHEET);
  hosp.clear();
  hosp.getRange(1, 1, 1, HOSPITAL_HEADERS.length)
      .setValues([HOSPITAL_HEADERS])
      .setFontWeight('bold');
  hosp.setFrozenRows(1);
  // Remove any pre-existing filter; createFilter throws if one already exists.
  const existingFilter = hosp.getFilter();
  if (existingFilter) existingFilter.remove();
  hosp.getRange('A:K').createFilter();

  let over = ss.getSheetByName(OVERRIDES_SHEET);
  if (!over) over = ss.insertSheet(OVERRIDES_SHEET);
  over.clear();
  over.getRange(1, 1, 1, OVERRIDE_HEADERS.length)
      .setValues([OVERRIDE_HEADERS])
      .setFontWeight('bold');
  over.setFrozenRows(1);

  // hospital_name (ref) auto-populates from the Hospitals tab.
  over.getRange('B2:B').setFormula(
    `=IF(A2="","",IFERROR(VLOOKUP(A2,${HOSPITALS_SHEET}!A:B,2,FALSE),"⚠ cnes not found"))`
  );

  // Lat / lng validation: Brazil bounding box + numeric.
  const latRule = SpreadsheetApp.newDataValidation()
      .requireNumberBetween(LAT_MIN, LAT_MAX)
      .setHelpText(`Latitude must be between ${LAT_MIN} and ${LAT_MAX} (Brazil).`)
      .setAllowInvalid(false).build();
  const lngRule = SpreadsheetApp.newDataValidation()
      .requireNumberBetween(LNG_MIN, LNG_MAX)
      .setHelpText(`Longitude must be between ${LNG_MIN} and ${LNG_MAX} (Brazil).`)
      .setAllowInvalid(false).build();
  over.getRange('C2:C').setDataValidation(latRule);
  over.getRange('D2:D').setDataValidation(lngRule);

  // Community Notes tab — additive layer, never mutates official fields.
  let notes = ss.getSheetByName(COMMUNITY_NOTES_SHEET);
  if (!notes) notes = ss.insertSheet(COMMUNITY_NOTES_SHEET);
  notes.clear();
  notes.getRange(1, 1, 1, COMMUNITY_NOTE_HEADERS.length)
       .setValues([COMMUNITY_NOTE_HEADERS])
       .setFontWeight('bold');
  notes.setFrozenRows(1);

  // hospital_name (ref) auto-populates from the Hospitals tab.
  notes.getRange('B2:B').setFormula(
    `=IF(A2="","",IFERROR(VLOOKUP(A2,${HOSPITALS_SHEET}!A:B,2,FALSE),"⚠ cnes not found"))`
  );
  // Category dropdown.
  const categoryRule = SpreadsheetApp.newDataValidation()
      .requireValueInList(COMMUNITY_NOTE_CATEGORIES, true)
      .setHelpText('Categoria: ' + COMMUNITY_NOTE_CATEGORIES.join(' / '))
      .setAllowInvalid(false).build();
  notes.getRange('C2:C').setDataValidation(categoryRule);

  SpreadsheetApp.getUi().alert(
    'Sheet setup complete. Next: run SoroJá → Refresh hospitals list.'
  );
}


// ---------------------------------------------------------------------------
// Refresh Tab 1 from live hospitals.json
// ---------------------------------------------------------------------------

function refreshHospitals() {
  const resp = UrlFetchApp.fetch(RAW_HOSPITALS_URL, { muteHttpExceptions: true });
  if (resp.getResponseCode() !== 200) {
    throw new Error(`Failed to fetch hospitals.json: HTTP ${resp.getResponseCode()}`);
  }
  const records = JSON.parse(resp.getContentText());

  const rows = records.map((h, i) => {
    const row = i + 2; // header is row 1
    return [
      h.cnes || '',
      h.hospital_name || '',
      h.state || '',
      h.city || '',
      h.address || '',
      h.lat,
      h.lng,
      h.geocode_tier,
      // Column I — current pin
      `=HYPERLINK("https://www.google.com/maps?q="&F${row}&","&G${row},"View pin")`,
      // Column J — search the displayed address
      `=HYPERLINK("https://www.google.com/maps/search/?api=1&query="&ENCODEURL(B${row}&", "&D${row}&", "&C${row}),"Find correct pin")`,
      // Column K — overridden flag
      `=IF(ISNUMBER(MATCH(A${row},${OVERRIDES_SHEET}!A:A,0)),"✓ overridden","")`,
    ];
  });

  const ss = SpreadsheetApp.getActive();
  const hosp = ss.getSheetByName(HOSPITALS_SHEET);
  if (!hosp) throw new Error(`Missing "${HOSPITALS_SHEET}" tab — run Setup first.`);

  // Clear any existing data rows (keep header row 1).
  const lastRow = hosp.getLastRow();
  if (lastRow > 1) {
    hosp.getRange(2, 1, lastRow - 1, HOSPITAL_HEADERS.length).clearContent();
  }

  if (rows.length) {
    hosp.getRange(2, 1, rows.length, HOSPITAL_HEADERS.length).setValues(rows);
  }

  SpreadsheetApp.getUi().alert(`Refreshed ${rows.length} hospitals from production.`);
}


// ---------------------------------------------------------------------------
// Publish overrides to GitHub
// ---------------------------------------------------------------------------

function publishOverrides() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  const repo = props.getProperty('GITHUB_REPO');
  if (!token || !repo) {
    throw new Error(
      'Missing script properties GITHUB_TOKEN and/or GITHUB_REPO. ' +
      'Open Project Settings → Script properties to add them.'
    );
  }

  const ss = SpreadsheetApp.getActive();
  const over = ss.getSheetByName(OVERRIDES_SHEET);
  if (!over) throw new Error(`Missing "${OVERRIDES_SHEET}" tab — run Setup first.`);

  const lastRow = over.getLastRow();
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert('No overrides to publish — Overrides tab is empty.');
    return;
  }

  const values = over.getRange(2, 1, lastRow - 1, OVERRIDE_HEADERS.length).getValues();
  const payload = {};
  const toMarkPublished = []; // row numbers (1-based) that should flip to "published"

  for (let i = 0; i < values.length; i++) {
    const r = values[i];
    const rowNum = i + 2;
    const [cnesRaw, , lat, lng, addressRaw, noteRaw, reason, verifiedOn, status] = r;
    const cnes = String(cnesRaw || '').trim();
    if (!cnes) continue; // blank row

    const latBlank = lat === '' || lat === null || lat === undefined;
    const lngBlank = lng === '' || lng === null || lng === undefined;
    const address = String(addressRaw || '').trim();
    const note = String(noteRaw || '').trim();

    if (latBlank !== lngBlank) {
      throw new Error(`Row ${rowNum}: lat and lng must both be set or both blank.`);
    }
    const hasCoords = !latBlank && !lngBlank;
    if (hasCoords) {
      if (typeof lat !== 'number' || typeof lng !== 'number') {
        throw new Error(`Row ${rowNum}: lat/lng must be numeric.`);
      }
      if (lat < LAT_MIN || lat > LAT_MAX || lng < LNG_MIN || lng > LNG_MAX) {
        throw new Error(`Row ${rowNum}: lat/lng outside Brazil bounding box.`);
      }
    }
    if (!hasCoords && !address && !note) {
      throw new Error(`Row ${rowNum}: provide corrected coordinates, a corrected address, a corrected note, or any combination.`);
    }
    if (!String(reason || '').trim()) {
      throw new Error(`Row ${rowNum}: reason is required.`);
    }

    const entry = {
      reason: String(reason).trim(),
      verified_on: verifiedOn ? formatDate_(verifiedOn) : '',
    };
    if (hasCoords) {
      entry.lat = lat;
      entry.lng = lng;
    }
    if (address) {
      entry.address = address;
    }
    if (note) {
      entry.note = note;
    }
    payload[cnes] = entry;

    if (status !== 'published') toMarkPublished.push(rowNum);
  }

  const count = Object.keys(payload).length;
  const ui = SpreadsheetApp.getUi();
  const confirm = ui.alert(
    'Publish overrides',
    `About to publish ${count} override(s) to ${repo}. Continue?`,
    ui.ButtonSet.YES_NO
  );
  if (confirm !== ui.Button.YES) return;

  const json = JSON.stringify(payload, null, 2) + '\n';
  const result = putFile_(repo, OVERRIDES_PATH, json, token,
    `Update location overrides (${count} entr${count === 1 ? 'y' : 'ies'}) via sheet`
  );

  // Mark rows as published.
  const now = new Date();
  for (const rowNum of toMarkPublished) {
    over.getRange(rowNum, OVERRIDE_COL_STATUS).setValue('published');
    over.getRange(rowNum, OVERRIDE_COL_PUBLISHED_AT).setValue(formatDate_(now));
  }

  ui.alert(
    'Published',
    `Committed ${count} override(s) to ${repo}.\n\n` +
    `Commit: ${result.commit.sha.substring(0, 7)}\n\n` +
    `Vercel will deploy in ~1 minute.`,
    ui.ButtonSet.OK
  );
}


// ---------------------------------------------------------------------------
// Publish community notes to GitHub
//
// One row in the "Community Notes" tab = one dated relato. Multiple rows
// for the same CNES become an array of notes on the published JSON.
// public_summary is maintainer-authored canned text — never raw user
// reports — and is capped at 280 characters at the validator gate.
// ---------------------------------------------------------------------------

function publishCommunityNotes() {
  const props = PropertiesService.getScriptProperties();
  const token = props.getProperty('GITHUB_TOKEN');
  const repo = props.getProperty('GITHUB_REPO');
  if (!token || !repo) {
    throw new Error(
      'Missing script properties GITHUB_TOKEN and/or GITHUB_REPO. ' +
      'Open Project Settings → Script properties to add them.'
    );
  }

  const ss = SpreadsheetApp.getActive();
  const notes = ss.getSheetByName(COMMUNITY_NOTES_SHEET);
  if (!notes) throw new Error(`Missing "${COMMUNITY_NOTES_SHEET}" tab — run Setup first.`);

  const lastRow = notes.getLastRow();
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert('Sem relatos para publicar — a aba Community Notes está vazia.');
    return;
  }

  const values = notes.getRange(2, 1, lastRow - 1, COMMUNITY_NOTE_HEADERS.length).getValues();
  const grouped = {}; // cnes -> [note, ...]
  const toMarkPublished = [];
  let totalNotes = 0;

  for (let i = 0; i < values.length; i++) {
    const r = values[i];
    const rowNum = i + 2;
    const [cnesRaw, , categoryRaw, reportedAtRaw, summaryRaw, expiresAtRaw, status] = r;
    const cnes = String(cnesRaw || '').trim();
    if (!cnes) continue; // blank row

    const category = String(categoryRaw || '').trim();
    if (!category) {
      throw new Error(`Row ${rowNum}: category is required.`);
    }
    if (COMMUNITY_NOTE_CATEGORIES.indexOf(category) < 0) {
      throw new Error(
        `Row ${rowNum}: category "${category}" is not allowed. ` +
        `Use one of: ${COMMUNITY_NOTE_CATEGORIES.join(', ')}.`
      );
    }

    if (!reportedAtRaw) {
      throw new Error(`Row ${rowNum}: reported_at is required.`);
    }
    const reportedAt = formatDate_(reportedAtRaw);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(reportedAt)) {
      throw new Error(`Row ${rowNum}: reported_at must be a valid date.`);
    }

    const summary = String(summaryRaw || '').trim();
    if (!summary) {
      throw new Error(`Row ${rowNum}: public_summary is required.`);
    }
    if (summary.length > COMMUNITY_NOTE_SUMMARY_MAX) {
      throw new Error(
        `Row ${rowNum}: public_summary is ${summary.length} chars; ` +
        `max is ${COMMUNITY_NOTE_SUMMARY_MAX}.`
      );
    }

    const entry = {
      category: category,
      reported_at: reportedAt,
      public_summary: summary,
    };

    if (expiresAtRaw) {
      const expiresAt = formatDate_(expiresAtRaw);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(expiresAt)) {
        throw new Error(`Row ${rowNum}: expires_at must be a valid date when set.`);
      }
      if (expiresAt <= reportedAt) {
        throw new Error(`Row ${rowNum}: expires_at must be after reported_at.`);
      }
      entry.expires_at = expiresAt;
    }

    if (!grouped[cnes]) grouped[cnes] = [];
    grouped[cnes].push(entry);
    totalNotes += 1;

    if (status !== 'published') toMarkPublished.push(rowNum);
  }

  const cnesCount = Object.keys(grouped).length;
  const ui = SpreadsheetApp.getUi();
  if (totalNotes === 0) {
    ui.alert('Sem relatos para publicar — verifique a aba Community Notes.');
    return;
  }
  const confirm = ui.alert(
    'Publicar relatos da comunidade',
    `Publicar ${totalNotes} relato(s) referente(s) a ${cnesCount} hospital(is) em ${repo}?`,
    ui.ButtonSet.YES_NO
  );
  if (confirm !== ui.Button.YES) return;

  const payload = {
    generated_at: formatDate_(new Date()),
    notes: grouped,
  };
  const json = JSON.stringify(payload, null, 2) + '\n';
  const result = putFile_(repo, COMMUNITY_NOTES_PATH, json, token,
    `Update community notes (${totalNotes} relato${totalNotes === 1 ? '' : 's'}) via sheet`
  );

  // Mark rows as published.
  const now = new Date();
  for (const rowNum of toMarkPublished) {
    notes.getRange(rowNum, COMMUNITY_NOTE_COL_STATUS).setValue('published');
    notes.getRange(rowNum, COMMUNITY_NOTE_COL_PUBLISHED_AT).setValue(formatDate_(now));
  }

  ui.alert(
    'Publicado',
    `Commit: ${result.commit.sha.substring(0, 7)}\n\n` +
    `${totalNotes} relato(s) em ${cnesCount} hospital(is). Vercel deploys in ~1 minute.`,
    ui.ButtonSet.OK
  );
}


// ---------------------------------------------------------------------------
// GitHub API helpers
// ---------------------------------------------------------------------------

function putFile_(repo, path, content, token, message) {
  const apiBase = `https://api.github.com/repos/${repo}/contents/${path}`;
  const headers = {
    'Authorization': `token ${token}`,
    'Accept': 'application/vnd.github+json',
  };

  // GET current sha (may 404 on first publish — then no sha needed).
  let sha = null;
  const getResp = UrlFetchApp.fetch(apiBase, { headers, muteHttpExceptions: true });
  if (getResp.getResponseCode() === 200) {
    sha = JSON.parse(getResp.getContentText()).sha;
  } else if (getResp.getResponseCode() !== 404) {
    throw new Error(`GitHub GET failed: HTTP ${getResp.getResponseCode()} — ${getResp.getContentText()}`);
  }

  const body = {
    message: message,
    content: Utilities.base64Encode(content, Utilities.Charset.UTF_8),
    branch: 'main',
  };
  if (sha) body.sha = sha;

  const putResp = UrlFetchApp.fetch(apiBase, {
    method: 'put',
    contentType: 'application/json',
    headers: headers,
    payload: JSON.stringify(body),
    muteHttpExceptions: true,
  });
  if (putResp.getResponseCode() >= 300) {
    throw new Error(`GitHub PUT failed: HTTP ${putResp.getResponseCode()} — ${putResp.getContentText()}`);
  }
  return JSON.parse(putResp.getContentText());
}


function formatDate_(d) {
  const date = d instanceof Date ? d : new Date(d);
  if (isNaN(date.getTime())) return String(d);
  const tz = Session.getScriptTimeZone();
  return Utilities.formatDate(date, tz, 'yyyy-MM-dd');
}
