# Hyperframes Composition Brief: Grok Invoices

## Objective
Create a short launch-style brag video for Grok Invoices, in the tone of a YC Demo Day film.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 22.5 seconds

## Source Material
- Project root: the Grok Invoices repo
- Primary files read: `README.md`, `apps/web/src/styles.css`, `apps/web/src/App.jsx`, `apps/web/src/domain.js`, `apps/web/src/CaseDrawer.jsx`, `assets/icon.svg`, `apps/web/public/assets/summary-*.png`
- Product name: Grok Invoices
- Tagline / strongest claim: Agents book purchase invoices from KSeF. No tax treatment is inferred from the supplier.
- Key UI or visual moment to recreate: the Invoices dashboard and the DEMO-003 fuel case
- Copy that must appear verbatim:
  - A fuel invoice arrived.
  - The car did not.
  - Grok Invoices
  - Agents book purchase invoices from KSeF.
  - Track every invoice, question, and accounting decision.
  - 2 / Completed, 1 / Waiting for client, 1 / Blocked
  - Demo Fuel Station
  - PLN 246.00
  - Unknown vehicle
  - DEMO-003
  - Which vehicle does this fuel purchase concern, how is it used, and what was the business purpose?
  - Awaiting context
  - No tax treatment is inferred from the supplier.
  - Agent as a Service.

## Creative Direction
- Tone preset: yc-parody
- Creative direction: YC Demo Day launch. Deadpan, specific, and proud of the real product.
- Interpretation: Hard cuts, one claim a scene, sentence case, no fake metrics, no wink.
- Angle: A fuel invoice shows up and the car does not. The agent asks. It does not guess the tax.
- Hook: A fuel invoice arrived. The car did not.
- Outro / punchline: Grok Invoices. Agent as a Service.
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign
  - Invented accuracy stats, city counts, or a completed tax decision
  - Secrets, tokens, phone numbers, real taxpayer identities

## Visual Identity
- Background: #eceeed
- Text: #171819
- Accent: #0750eb, waiting badge #ffebbd / #46350f, mark #c026d3
- Display font: Inter
- Body font: Inter, data in IBM Plex Mono
- Visual references from the project: white shell with an 8px frame and 36px radius, pastel summary-card photos, status pills, GI mark

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. The problem — 3.55s — two hook lines
2. The name — 3.80s — mark, name, KSeF line
3. The inbox — 6.21s — three counts, then the PLN 246.00 row
4. The question — 5.54s — the vehicle question, then the no-inference line
5. The name again — 3.40s — Grok Invoices / Agent as a Service

## Audio
- Audio role: warm bed
- Audio arc: bed throughout, clicks in the inbox, two soft hits, fade on the last second and a half
- Music: `assets/music/happy-beats-business-moves-vol-10-by-ende-dot-app.mp3`
- Music treatment: gain about 0.34, fade-in 0.3s, fade-out 1.4s
- Music cue guidance: skill preset for vol. 10, ~110 BPM. Lock reasoning to 15.82s and the tagline to 20.19s. Cards on 7.79 / 8.73 / 9.83, row on 10.93.
- Audio-reactive treatment: none. Extraction helper from the older media-use path is not in the current skill, and this run does not sign in to HeyGen to fetch a different track. Documented skip, not a waveform.
- Audio-coupled moments:
  - inbox cards and row — short clicks
  - reasoning line — soft impact at 15.82s
  - tagline — soft impact at 20.19s
- SFX selection guidance: low high-frequency-risk files from the skill analysis. Clicks for arrivals, `impactSoft_medium_*` for the two payoffs.
- SFX analysis guidance: `.agents/skills/brag/assets/sfx/sfx-analysis.md`
- Exact SFX choice: `click2.ogg`, `click_003.ogg`, `click_002.ogg`, `click_005.ogg`, `impactSoft_medium_001.ogg`, `impactSoft_medium_004.ogg`
- Audio files: music and SFX live in `brag-output/composition/assets/`

## Hyperframes Instructions
Brag plan and this brief replace the storyline, SPEC, and LOOK steps. Check is the gate. Keep the render local.

Requirements:
- Show the real dashboard and the real DEMO-003 question.
- Keep all text readable.
- 22.5 seconds, inside 15–25.
- Music and the sparse SFX above.
- Beat-lock only the reasoning line and the tagline.
- Do not publish.


## Color and motion revision
LOOK: dashboard cyan #9ee9f3, blue #b4caff, peach #ffd7b0 and pink #e9bcea on #f6f3ef; Inter 900 titles, IBM Plex Mono invoice details. Continuous slow gradient drift, 0.5s spring card entrances, blue and magenta emphasis, and animated progress rules. Keep the original 22.5s story and audio cues. Synthetic product illustration, not a live integration recording.

Final editing pass: see blank-page-edit.md. Progress rules and eyebrow labels removed; camera pushes toward the fuel row and cuts to a larger question panel.
