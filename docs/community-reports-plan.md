# SoroJá Community Reports & Product Feedback Plan

This document captures a product and data-governance proposal for handling two distinct kinds of community input on SoroJá while keeping the site simple, lightweight, and grounded in the official Ministry of Health source:

1. **Community data reports** — corrections, missing hospitals, and source contributions.
2. **Product feedback** — UX bugs, feature requests, general comments.

No code or publishing action is implied by this plan.

_Last updated: 2026-04-21. Supersedes earlier drafts; reflects the full Bug Reports DB (including resolved items) and the Improvements page._

## Context

SoroJá uses Ministry of Health PESA data as the primary source of truth. The app publishes a static `hospitals.json` and shows the official source date on hospital cards.

Users across Brazil send feedback from the ground: wrong pins, incorrect phone area codes, closed units, missing hospitals, alternative state-level sources, and UX/feature suggestions. 100% of today's intake arrives via the maintainer's personal WhatsApp and is triaged in a personal Notion workspace.

The challenge: let useful local knowledge reach users quickly without:

- making the maintainer the bottleneck for every update;
- silently overriding official Ministry of Health data;
- creating liability by presenting unverified reports as fact;
- collecting personal data or creating LGPD exposure;
- making the app heavier or dependent on a live database during emergencies;
- deepening personal-account dependencies that cannot be handed off.

## Guiding principles

1. **Static-first, offline-capable.** The emergency path keeps working even if intake/backend is down.
2. **Official data remains canonical.** Community input never silently mutates `hospitals.json`. It appears as a visibly distinct layer.
3. **Depersonalized infrastructure.** Intake and triage sit on project-owned infrastructure (the `sos-antiveneno` GitHub repo), not on the maintainer's personal WhatsApp or Notion. Personal channels migrate out of the critical path over time.
4. **Two pipelines, not one.** Data reports and product feedback have different consumers, different surfaces, and different trust models. Treat them separately even if the intake form is shared.

## What the actual feedback data shows

Reviewing the full Bug Reports database (resolved + open) and the Improvements page. The shape is much more diverse than a first glance at open items suggests.

**Data-correction reports (the majority of actionable traffic):**

- Wrong map pin / location (UPA Galba Novaes, UPA Cascatinha, UPA São Francisco Xavier SJC)
- Wrong phone / DDD (Hospital PS Juiz de Fora — resolved, commit f5a7861's neighborhood)
- Wrong city association (Araçatuba/SP shown as Araraquara/SP)
- Wrong unit at an address (UPA Central Araraquara: wrong UPA / carries antifungal, not antiveneno)
- Listed open but actually closed (Canoas/RS)
- Missing hospital (Governador Valadares Hospital Municipal; Hospital da Primavera, Teresina-PI)

**Data-source contributions** (a category to handle explicitly):

- Enrico (médico, ES) shared two authoritative state-level sources: `vacinaeconfia.saude.es.gov.br/transparencias/pontos_soro/` and the CIATox ES PDF. These aren't per-hospital corrections — they're alternative source-of-truth pointers that can enrich or replace the PESA extract for a given state.
- Similar pattern: the DF reporter shared `saude.df.gov.br` PDFs for Distrito Federal.

**UX bugs and quality issues:**

- Filtros: lista SP só aparece após recarregar (filter/state listing race)
- Flavia (RJ): no clear search button, "feels like I'm guessing," cluttered layout, emojis too small in panic moments, map doesn't center on searched city
- Silvana, Tia Fernanda (Belém): similar-shape raw reports

**Feature suggestions** (multiple convergent signals on UX gaps):

- Emergency-order popup (community-sourced medical guidance): *"1) Ligar SAMU/bombeiros. 2) Ligar CIATox. 3) Só depois ir ao local com soro."* — this is medically more correct than the generic "ligue antes de ir" phrasing.
- CIATox (Centros de Informação e Assistência Toxicológica) integration / reference.
- Larger soro-type icons on hospital cards (Allan Martinho, Flavia — convergent).
- "Como chegar" button should use Google Maps icon for instant recognition (Allan).
- Limit map markers to a ~200km radius around the user/searched city (Sergio Bastos; aligns with Flavia's "mapa do país inteiro" complaint).
- Search should accept a city name even when no hospital matches there, and return nearest hospitals.
- Brasília/DF data incomplete; city search within state doesn't surface it.
- Project Instagram with link in bio, for reach in contexts where people type the URL wrong (Juliana).

**Positive/encouragement comments** (tracked for morale, not public):

- Parabéns / compartilhando mentions from most reporters.

Implications for the plan:

1. Data-correction volume is real and present, not speculative. Per-hospital reports already outnumber open UX complaints. The community-reports layer is justified by current signal, not future guesses.
2. **Multiple users converging on the same UX issues** (icon size, map radius, search flow) is a strong signal that those specific fixes should ship soon — they're not opinions, they're consensus.
3. "Data source contributions" is its own category that needs a destination. Enrico's ES sources aren't a "relato da comunidade" on one hospital — they're a pointer to an alternative state-of-truth. Handle this as a separate intake path (see below).
4. The community-authored emergency-order popup is more correct than the generic disclaimer I earlier proposed. Use *their* wording, not mine.
5. CIATox is the medical-expertise layer for envenomation in Brazil. Adding CIATox state phone numbers to every hospital card may be higher-leverage than any of the above.

## Report taxonomy

Intake form routes each submission into one of these categories. Each category has a different downstream path.

| # | Category (PT-BR user-facing) | Internal type | Downstream |
|---|---|---|---|
| 1 | Telefone, endereço ou horário errado | `data:contact_fix` | Community report → verified override |
| 2 | Localização no mapa parece errada | `data:pin_fix` | Community report → verified override |
| 3 | Este hospital/UPA está fechado ou não atende | `data:closed` | Community report (volatile, expires) |
| 4 | Hospital listado é o errado (unidade trocada) | `data:wrong_unit` | Community report → escalated manual review |
| 5 | Hospital faltando na lista | `data:missing_hospital` | Community report (new entry) |
| 6 | Tenho uma fonte oficial melhor (link/PDF) | `data:source_contribution` | Maintainer queue (not public) |
| 7 | Confirmado que este local atende normalmente | `data:confirmation` | Positive signal aggregator |
| 8 | Problema no site / sugestão / bug | `product:ux` | GitHub Issues `type:ux` |
| 9 | Sugestão de nova funcionalidade | `product:feature` | GitHub Issues `type:feature` |
| 10 | Outro | `other` | Triage queue |

Category 7 (user confirms "this place really does have what the site says") is a useful signal not in today's inbox, but worth collecting to build positive freshness signals, not just negative ones.

## Core recommendation

Three-layer data model, two-pipeline intake.

### Three-layer data model

1. **Official layer** — Ministry of Health / PESA data. Canonical base dataset. UI continues to show source and source date.
2. **Community report layer** — anonymous, structured, dated reports. Publicly visible as compact summaries. Clearly labeled unverified. Raw submissions never shown publicly.
3. **Verified correction layer** — reports later validated by the maintainer become manual overrides via the existing `data/location_overrides.json` pattern. Original official source stays traceable.

### Two pipelines

- **Pipeline A — Community data reports** (categories 1–7): feed into a sanitized `app/community_reports.json`, which renders on hospital cards and in missing-hospital sections.
- **Pipeline B — Product feedback** (categories 8–9, and 10 by routing): feed directly into GitHub Issues with labels. Not rendered on the public site (maybe a roadmap page, see Improvements below).

Category 6 (**data source contributions**) is special: it's not a per-hospital relato, and it shouldn't render on the site. It flows into a private maintainer queue (GitHub Issues with label `data:source_contribution`) for future pipeline work — e.g., swapping the PESA extract for ES with Enrico's state transparency page would be a scripts/data update, not a community-reports render.

## Product principle

Use the word **"relato"**, not "comentário" or "correção." *Relato* = useful field signal, not necessarily an official correction. Suggested label: **"Relatos da comunidade."**

Avoid in V1:

- open comment threads; public raw messages; public reporter names; public phone numbers; public screenshots; anything that looks like a social feed.

## Public display model (community reports layer)

Compact summaries, not raw comments. Canned summary strings per category:

For an existing official hospital:

> Relato da comunidade em 20/04/2026: este local pode estar fechado. Informação não confirmada pelo Ministério da Saúde. Em emergência, ligue 192 e confirme antes de se deslocar.

For a possible missing hospital:

> Relatado pela comunidade: Hospital X, Cidade/UF. Este local não consta na fonte oficial usada pelo SoroJá. Confirme com SAMU/CIATox antes de se deslocar.

Multiple reports aggregated:

> 2 relatos recentes. Último relato: 20/04/2026. Comunidade informou possível erro de localização.

Positive confirmation (category 7):

> Última confirmação da comunidade: 20/04/2026 — o local atendeu normalmente.

## Missing hospitals

Visible immediately, but separated from official results.

Section header: **"Locais relatados pela comunidade, ainda não oficiais"**

Visually distinct from official hospitals (amber badge / marker). Collapsed by default, shown below official results for the relevant city/state.

Disclaimer:

> Este local foi relatado pela comunidade e ainda não consta na fonte oficial usada pelo SoroJá.

## Report intake form (in-app)

The intake form is the single user-facing entrypoint, regardless of category. One form, clear category picker, structured-only input.

Shared fields:

- Category (from the taxonomy above)
- Target: auto-filled if report is launched from a hospital card (CNES + name); user-entered for missing-hospital reports
- Quando você percebeu isso? (Hoje / Últimos 7 dias / Mais antigo / Não sei)
- Short structured observation (category-specific short text — not a free-text paragraph in V1)
- Google Maps link for location evidence (optional, for `data:pin_fix` and `data:missing_hospital`)
- Checkbox: *"Não inclui dados pessoais ou informações de paciente."*

Category-specific follow-up fields for missing hospitals (category 5):

- Estado
- Cidade
- Nome do hospital/unidade
- Endereço ou bairro (opcional)
- Google Maps link (opcional)
- Tipo de acidente/soro que atende (opcional, rotulado com cuidado)

Category-specific for data source contributions (category 6):

- UF(s) que a fonte cobre
- Tipo de fonte (site oficial do estado / PDF / CIATox / outra)
- URL
- Breve observação (opcional)

Avoid asking for:

- name; phone; email; profession; patient details; medical history; photos/screenshots in V1.

If the user wants to provide contact for follow-up, make it opt-in and explicitly scoped to "você concorda em ser contatado(a) caso precisemos validar?"

## LGPD-minimal direction

Not legal advice. The product intentionally avoids collecting personal data.

- Do not ask for name, phone, email, or professional role by default.
- Do not publish raw free text.
- Do not allow image uploads in V1.
- Visible note: *"Não envie dados pessoais, informações de paciente, telefone, e-mail ou nomes."*
- Store only: structured category, target, report date, optional non-personal location evidence (Maps link), opt-in contact (only if provided and separately consented).

Caveat: backend tooling can create technical logs (IP, user agent). Pick infrastructure and retention with that in mind. GitHub Issues retains submitter metadata for the bot account only; anonymous submissions leave no direct PII trail on the issue body itself, provided the bot posts on behalf of the user.

References:

- ANPD glossary: https://www.gov.br/anpd/pt-br/centrais-de-conteudo/materiais-educativos-e-publicacoes/glossario-anpd/d
- LGPD: https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm

## Freshness and expiration

*Volatile* (change quickly):

- hospital may be closed today; phone didn't answer; staff redirected elsewhere; unit may not have serum right now.

*Stable*:

- wrong pin; wrong DDD; wrong address; missing hospital; wrong unit; duplicate/wrong name.

Freshness rules:

- **Stable categories**: keep visible until resolved or superseded.
- **Hospital closed / may not attend**: prominent for 30 days; downgrade to "relato antigo" after 30; hide from default view after 90 unless repeated.
- **Phone did not answer**: 14–30 days; phrase *"recomenda-se confirmar por telefone"*, never as proof.
- **Serum availability**: avoid "sem soro"; safer wording *"relato recente recomenda confirmar disponibilidade antes de se deslocar."*
- **Positive confirmations**: surface the latest confirmation date per hospital; decays at 90 days.

## Architecture (GitHub-native, depersonalized)

Keep the app static-first. Route intake and triage through the project-owned `sos-antiveneno` repo, not personal accounts.

**Public-site files:**

- `app/hospitals.json` — official + verified data. Current production contract, unchanged.
- `app/community_reports.json` — sanitized, public, anonymous report summaries (Pipeline A output). Loaded client-side *after* `hospitals.json`. If it fails to load, the app still works as today.

**Intake pipeline:**

- In-app form (vanilla JS, no new frontend deps) → one Vercel serverless function (`api/report.js`) → GitHub REST API opens an issue on the repo.
- Authentication: dedicated GitHub App or fine-grained PAT, scoped only to Issues-write on the one repo. Stored as a Vercel env var.
- Label schema: `type:data` vs `type:product`, plus a category label (`data:pin_fix`, `data:closed`, `product:ux`, `product:feature`, etc.), plus `cnes:<id>` where applicable, plus `uf:<state>` for state-level items.
- Rate-limited by IP at the function boundary.

**Triage:**

- GitHub Issues with label filters and/or a Projects board.
- Handoff-ready from day one: adding a collaborator is the whole onboarding step.
- Replaces Notion as the canonical intake surface. Notion can still hold private maintainer notes; it is no longer load-bearing.

**Publishing `community_reports.json`:**

Two paths, choose one:

- *Path A — auto-generated*: a GitHub Action reads closed/labeled Issues, emits sanitized `community_reports.json`, commits, Vercel redeploys. Low-touch.
- *Path B — manual curation*: the maintainer edits `community_reports.json` during weekly review, same pattern as `location_overrides.json`. Higher trust gate, slower.

Start with Path B; upgrade to Path A once there are >~20 active reports and stable category wording.

Schema for the sanitized file:

```json
{
  "generated_at": "2026-04-21",
  "reports": [
    {
      "target_type": "hospital",
      "cnes": "1234567",
      "category": "possibly_closed",
      "latest_reported_at": "2026-04-20",
      "report_count": 2,
      "public_summary": "Comunidade informou que este local pode estar fechado. Confirme antes de se deslocar.",
      "expires_at": "2026-05-20"
    },
    {
      "target_type": "missing_hospital",
      "state": "PI",
      "city": "Teresina",
      "name": "Hospital da Primavera",
      "category": "missing_hospital",
      "latest_reported_at": "2026-04-19",
      "report_count": 1,
      "public_summary": "Este local foi relatado pela comunidade e ainda não consta na fonte oficial usada pelo SoroJá."
    }
  ]
}
```

The public site consumes only the sanitized JSON, never the raw intake store.

## Publishing policy

- **Structured summaries** (category + target + date + canned wording) auto-publish. Already sanitized by construction.
- **Raw text** is never published. Ever.
- **Reporter identity** is never published. Ever.
- **Patient details** are never published. Ever.
- **Community reports stay visibly unofficial**, in their own layer, amber-coded, with a standing disclaimer.
- **Promotion to the verified layer** (modifying `location_overrides.json` or canonical data) happens only through the maintainer's existing review workflow, not automatically.
- **Source contributions** (category 6) do not publish anywhere — they enter a private maintainer queue.

## UI placement

**Phase 0 — standalone, ship first:**

- Community-sourced emergency-order popup/callout on every hospital card, using the medically-vetted wording:

  > **Antes de ir ao hospital:**
  > 1. Ligue para o SAMU (192) ou Bombeiros (193)
  > 2. Ligue para o CIATox do seu estado
  > 3. Só depois dirija-se a um local com soro

- Add CIATox state phone numbers to each hospital card (one extra field per state, not per hospital).
- Make the phone call button larger and more prominent. Use a Google Maps icon on the "Como chegar" button.
- Increase the soro-type icon size on hospital cards (convergent feedback from Allan + Flavia).

Each of these fixes comes directly from community input and should ship regardless of the rest of this plan.

**On each hospital card (Phase 2, after Pipeline A ships):**

- Small "Reportar erro" action.
- If reports exist, a compact "Relatos da comunidade" row below the address/source area. Details collapsed by default.
- Latest positive confirmation (if any): *"Última confirmação da comunidade: 20/04/2026."*

**On empty or weak search results:**

- "Não encontrou um hospital? Enviar relato."
- Show nearby official hospitals first.
- Then "Locais relatados pela comunidade, ainda não oficiais."
- When a searched city has no hospital, automatically fall through to nearest neighbors (requested by `+55 61 99925-2422`).

**On the map:**

- Default view constrained to ~200km radius around the user's location or searched city (requested by Sergio Bastos; convergent with Flavia's complaint).
- Official hospitals keep the normal marker.
- Community-only missing hospitals use a distinct marker color and label.
- Community-only hospitals are not mixed into "hospital mais próximo" without a strong disclaimer.

## Product feedback surface (Pipeline B)

Product feedback (UX bugs, feature requests) flows into GitHub Issues with `type:product` and a subcategory label. No public render by default.

Optional public artifact: a simple `docs/roadmap.md` or a pinned GitHub Issue listing "Próximas melhorias" — sourced from community suggestions, with attribution where the reporter consented. Addresses Juliana's Instagram-style "show the project is alive" concern without building a social presence.

## Trust and safety rules

- Block public summaries that would include phone numbers, emails, CPF-like patterns, or patient-identifying phrases. Enforced by construction: only canned summaries publish.
- Rate-limit submissions at the serverless function.
- Private abuse/removal mechanism: closing/hiding issues, regenerating `community_reports.json`.
- Standing disclaimer near community reports:

  > Os relatos da comunidade ajudam a sinalizar possíveis problemas nos dados, mas não substituem orientação médica nem fontes oficiais. Em emergência, ligue 192.

## Contact channel migration

Today the footer contact is the maintainer's personal WhatsApp. Migration path:

1. **Short term** — ship the in-app form (Phase 1). Keep the WhatsApp link visible but de-emphasize.
2. **Medium term** — replace personal WhatsApp with a project email (e.g., `contato@soroja.com.br`) that forwards wherever the maintainer wants. Decoupled from any individual phone.
3. **Long term (optional)** — project-owned WhatsApp Business number, only if voice-of-user demand justifies the maintenance.

Conversational channels stay as options, not as load-bearing intake.

## Phased rollout

**Phase 0 — Community-sourced immediate wins (days, not weeks)**

Ship, each as its own small PR, independent of any intake system:

- Emergency-order callout (SAMU → CIATox → hospital) on every hospital card.
- CIATox state phone numbers visible per hospital (shared data per state).
- Bigger soro-type icons, Google Maps icon on "Como chegar."
- Filtros: fix the SP-only-after-reload bug.
- Map radius constrained to ~200km default.
- City search falls through to nearest hospitals when no direct match.
- DF data gap: either ingest the shared DF/ES sources or acknowledge the gap.

These are the fixes already paid for in user-reported signal. Highest leverage for current users, zero new infrastructure.

**Phase 1 — Structured intake via GitHub Issues (1–2 days)**

- In-app "Reportar / Enviar feedback" button (per hospital card + footer general).
- Vanilla-JS modal with the ten-category picker and category-specific fields.
- One Vercel serverless function → GitHub Issues API with labels.
- Footer contact migrates off personal WhatsApp to project email (same PR or next).
- No public community-reports render yet. Goal: replace screenshot triage; surface real volume per category.

**Phase 2 — Public community-reports layer (Pipeline A)**

- Populate `app/community_reports.json` manually at first (Path B).
- Render "Relatos da comunidade" summaries and "Locais relatados pela comunidade" section.
- Positive confirmations (category 7) aggregator.
- Upgrade to auto-generation (Path A) when volume + category wording stabilize.

**Phase 3 — Trusted-contributor auto-promotion (optional)**

- Allowlist repeat contributors (e.g., health-system workers, ES doctor Enrico) whose reports promote to verified overrides without manual review.

**Phase 4 — Data source swap per state (driven by category 6 contributions)**

- Where state-level sources (e.g., ES, DF) are more current/complete than the national PESA PDF, add them as a new extractor in `scripts/` and merge into `hospitals.json` during rebuild. This is a script/data-pipeline change, distinct from the community-reports UI.

## Files impacted when implementation begins

- `app/index.html` — Phase 0 popup/callout + icon fixes + map radius + search fallback + DDI-size buttons; Phase 1 "Reportar" button + modal; Phase 2 community-reports rendering.
- `app/sw.js` — bump `CACHE_NAME` whenever HTML changes.
- `app/community_reports.json` (new, Phase 2).
- `app/ciatox.json` (new, Phase 0) — state-keyed CIATox phone numbers, shared across all hospitals in each state.
- `api/report.js` (new, Phase 1).
- `vercel.json` — enable serverless function routing.
- Vercel env: `GITHUB_BOT_TOKEN`.
- `.github/` — optional Action for Path A (Phase 2).
- `data/location_overrides.json` — unchanged; still the verified-layer store.
- `scripts/` — Phase 4 per-state source extractors (e.g., ES `vacinaeconfia.saude.es.gov.br`).
- `docs/roadmap.md` (optional) — public-facing list of next improvements, derived from Pipeline B.

## Open questions

1. Community-only missing hospitals on the map immediately, or list-only first?
2. One report enough to surface a missing hospital, or minimum 2?
3. Default expiration for "possibly closed": 30 / 60 / 90 days?
4. Optional free-text field even if never publicly shown? (Helps Pipeline B, neutral for Pipeline A.)
5. GitHub App vs fine-grained PAT for the bot token?
6. Rate-limit strictness on day one?
7. Does the footer contact migrate to `contato@soroja.com.br` in the Phase 1 PR or later?
8. Do we keep any of the old "possible private/raw store" list (Notion / Google Sheet / Supabase / Vercel/Edge) as alternatives, or is GitHub Issues the canonical single intake?
9. For category 6 source contributions: do we surface contributors publicly (with consent) as a data-provenance credit, or keep private?
10. Public roadmap page: is attribution by first name + UF acceptable (with consent), or fully anonymous?

## Preferred V1

Intentionally small and staged:

- **Phase 0 (ship first)** — Community-sourced immediate wins. None of these require any new infrastructure. All are already-paid-for improvements derived from current community signal.
- **Phase 1** — Anonymous structured intake → GitHub Issues. Ten-category picker. Migrate footer contact off personal WhatsApp.
- **Phase 2 (once intake data is flowing)** — Sanitized `community_reports.json`, public aggregate signal on hospital cards, "Locais relatados pela comunidade" section.

Avoid in V1: public raw text; reporter identity; contact info; screenshots; patient details; dependency on personal accounts.

This gives SoroJá a community feedback loop that honors current user input, keeps the site static and lightweight, and moves the infrastructure off any individual's personal accounts.
