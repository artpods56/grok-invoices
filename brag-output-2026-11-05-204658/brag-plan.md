# Brag Plan: Grok Invoices

## What is this app?
Grok Invoices is an Agent as a Service that books purchase invoices from KSeF. The demo a founder actually feels is a fuel invoice for an unknown vehicle: the agent asks which car it was, and it does not invent the tax treatment.

## The angle
YC Demo Day, played straight. One claim per cut. The product is a Polish founder's inbox, not a generic finance platform. The joke, if there is one, is how calmly the software refuses to guess.

## Hook (first 2-3 seconds)
A fuel invoice arrived. The car did not.

## Key moments (the middle)
- The real dashboard counts, from the synthetic fixtures: 2 Completed, 1 Waiting for client, 1 Blocked.
- DEMO-003 lands in the table: Demo Fuel Station, 2026-11-05, gross PLN 246.00, Waiting for client, Unknown vehicle.
- The agent's question, verbatim, then the product's own line: no tax treatment is inferred from the supplier.

## Outro / punchline
Grok Invoices. Agent as a Service.

## User flow worth showing
Invoice arrives in the inbox → the case is Waiting for client on an unknown vehicle → the agent asks which vehicle, how it is used, and the business purpose. The result on screen is the question, not a made-up booking.

## Tone
- Preset: yc-parody
- Creative direction: YC Demo Day launch. Deadpan, specific, and proud of the real product. Not a parody of the product.
- Interpretation: Hard cuts, one claim a scene, sentence case, heavy Inter for claims, IBM Plex Mono for invoice ids and amounts. No wink, no fake metrics.

## Format: landscape — 1920x1080
## Duration: 22.5

## Visual identity (from the project)
- Background: #eceeed
- Accent: #0750eb (active nav), waiting badge #ffebbd / #46350f, completed #dcefd4 / #1c361c, mark #c026d3
- Text: #171819
- Display font: Inter (700 / 900)
- Body font: Inter; data in IBM Plex Mono
- Strongest visual element: the light invoice shell — white 8px frame, pastel summary cards, one fuel row

## Share copy (draft)
We built Grok Invoices so a fuel invoice can ask which car it was. Agents book purchase invoices from KSeF. No tax treatment is inferred from the supplier.

## Audio direction
- Role: warm bed
- Music: happy-beats-business-moves-vol-10-by-ende-dot-app.mp3 (Sascha Ende, ende.app, CC BY 4.0)
- Music treatment: under the picture from the first frame, about 0.34 gain, short fade-in, fade out over the last 1.4s. Never covers the cuts.
- Music cue guidance: preset `assets/music/cues/happy-beats-business-moves-vol-10-by-ende-dot-app.music-cues.md` in the skill. Tempo about 110 BPM. Strong cues used: 15.82s (reasoning) and 20.19s (tagline). Beat grid for the three status cards: 7.79, 8.73, 9.83, then the invoice row at 10.93.
- Audio-reactive treatment: none. The media-use skill no longer ships the local RMS extractor this workflow asks for, and HeyGen catalog audio was not used. No waveform, no pulse substitute.
- SFX posture: sparse. Soft UI clicks on each card and the row. One warm impact on the reasoning line, one on the tagline.
- Audio-coupled moments: card sequence, invoice row, reasoning reveal, final tagline
- Restraint rule: no whooshes, no risers, no voiceover

## Storyboard

### Scene 1 — The problem — 3.55s
Light canvas. Two lines, left, heavy: "A fuel invoice arrived." then "The car did not."
Sequential/interaction: yes — the second line arrives on the 1.90s beat and both hold
Audio intent: the bed is already moving; no hit yet
Audio-coupled idea: none
Music: warm business bed
Transition mood: hard → Scene 2

### Scene 2 — The name — 3.80s
The GI mark and "Grok Invoices", then "Agents book purchase invoices from KSeF."
Sequential/interaction: yes — name, then the KSeF line
Audio intent: still the bed
Audio-coupled idea: none
Music: same bed
Transition mood: hard → Scene 3

### Scene 3 — The inbox — 6.21s
The invoice dashboard. Three summary cards arrive one by one (2 Completed, 1 Waiting for client, 1 Blocked), then the DEMO-003 row: Demo Fuel Station, PLN 246.00, Waiting for client, Unknown vehicle.
Sequential/interaction: yes — three cards, then the fuel row
Audio intent: a quiet click with each arrival
Audio-coupled idea: card-by-card, then the row
Music: same bed
Transition mood: hard → Scene 4

### Scene 4 — The question — 5.54s
The case speaks. "Which vehicle does this fuel purchase concern, how is it used, and what was the business purpose?" Then, on the 15.82s cue: "No tax treatment is inferred from the supplier."
Sequential/interaction: yes — question, then the refusal
Audio intent: one soft impact when the refusal lands
Audio-coupled idea: beat-locked reveal
Music: same bed
Transition mood: hard → Scene 5

### Scene 5 — The name again — 3.40s
GI mark. "Grok Invoices." The tagline "Agent as a Service." lands on the 20.19s cue and holds.
Sequential/interaction: yes — mark and name, then the tagline
Audio intent: one soft impact with the tagline, music fades
Audio-coupled idea: beat-locked tagline
Music: bed fading out
Transition mood: hard, then hold

**Music mood for this video:** upbeat, held back
**Audio summary:** A short business bed under hard cuts, with four quiet clicks and two soft hits, then a fade on the name.


## Color and motion revision
LOOK: dashboard cyan #9ee9f3, blue #b4caff, peach #ffd7b0 and pink #e9bcea on #f6f3ef; Inter 900 titles, IBM Plex Mono invoice details. Continuous slow gradient drift, 0.5s spring card entrances, blue and magenta emphasis, and animated progress rules. Keep the original 22.5s story and audio cues. Synthetic product illustration, not a live integration recording.

Final editing pass: see blank-page-edit.md. Progress rules and eyebrow labels removed; camera pushes toward the fuel row and cuts to a larger question panel.
