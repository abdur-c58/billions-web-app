---
name: ancient-britain-script-writer
description: Use this skill whenever the user wants to write, plan, or expand a video script or title for "Ancient Britain," a YouTube channel covering underreported British history — mysterious places, lost kingdoms, forgotten events, and stories most people were never properly taught. Trigger for requests to generate single-topic deep-dive scripts, title brainstorming, script expansion, or broll JSON for this channel. Also trigger when the user says "make new video," references "Ancient Britain," or asks to continue/expand a previous Ancient Britain script.
---

# Ancient Britain Script Writer

A skill for producing `script.json` files for **Ancient Britain**, a YouTube channel making ~17-minute narrated documentary-style videos about underreported British history. Each video covers a single location, event, figure, or mystery — told with archaeological precision and a voice that treats the audience as curious adults who have been let down by the history they were taught.

This file encodes the channel format, transcript-derived metrics, title formula, script voice and structure, Remotion composition rules, the full `script.json` schema, validation checklist, and topic rotation system.

Read this entire file before beginning any Ancient Britain task.

---

## TRANSCRIPT ANALYSIS (derived from Black Mountain episode)

This section records what was actually inferred from the provided channel transcript. All norms below come from measurement, not assumption.

| Metric | Value |
|---|---|
| Transcript word count | ~2,473 words |
| Estimated runtime at 145 wpm | ~17 minutes |
| Average segment length | ~85–110 words |
| Beats in episode | 8 |
| Remotion vs b-roll ratio | ~35% Remotion (overlays + split cards + full TitleCards), ~65% stock/commons |
| Remotion placement | Subscribe CTAs, mid-video CTAs, key facts, dates/names, chapter breaks, numbered lists |
| Subscribe CTA placement | Segment ~5–6 and mid-video — **always Remotion overlay popups**, never stock CTA footage |
| Title pattern | Specific place or event + layered mystery + implied resolution that surprises |

**Inferred narration speed:** 145 wpm (same as Apex Archives; consistent with documentary pacing).

**Remotion layouts observed / supported:**

1. **`overlay`** — full-frame b-roll with a large Remotion popup on top (lower-third, center, or top-banner). Use for subscribe CTAs, mid-video CTAs, quick facts, dates, names, and one-line revelations while landscape b-roll continues underneath.
2. **`split-right`** — b-roll left half, FactCard right half. Use for dense bullet lists that need a full side panel.
3. **`full`** — entire frame is Remotion (TitleCard chapter breaks, occasional full-screen FactCard).

**Default:** prefer `overlay` over `split-right` when the on-screen copy is short (title + 1–3 lines). Reserve `split-right` for longer bullet lists. Never fetch stock "subscribe CTA" footage — always use `remotion:FactCard` or `remotion:TitleCard` with `layout: "overlay"`.

---

## RUNTIME TARGET — READ THIS FIRST

**Target: 17 minutes at 145 wpm = 2,465 words minimum. Ideal range: 2,400–2,900 words.**

This is a tighter format than long-form documentary channels. Every segment must earn its runtime. Do not pad — deepen. Do not deliver under 2,200 words. Compute the word count explicitly before delivering and report it.

### Per-beat depth rules

| Beat | Segments | Words | Minutes |
|---|---|---|---|
| Hook | 2–3 | 220–280 | ~1.8 |
| Setting / geography | 2–3 | 190–260 | ~1.7 |
| Indigenous / ancient knowledge | 2–3 | 200–260 | ~1.7 |
| Colonial / historical record | 3–4 | 280–350 | ~2.2 |
| Folklore / mystery layer | 2–3 | 200–250 | ~1.6 |
| Mid-video CTA | 1 | 60–80 | ~0.5 |
| Scientific / historical investigation | 3–4 | 280–360 | ~2.3 |
| Real explanation + conclusion | 2–3 | 220–270 | ~1.7 |
| Outro | 1–2 | 100–140 | ~0.8 |
| **TOTAL** | **~22–26** | **~2,450–2,950** | **~17–20 min** |

**Every beat must be present.** A script missing the "indigenous / ancient knowledge" beat or the "scientific investigation" beat is incomplete — these are what separate Ancient Britain from surface-level mystery content.

### Why scripts come in short and how to fix it

The failure mode is beats that name a fact but don't explain the mechanism behind it, the context around it, or the implication of it. For every claim in the script, ask: *Why does this matter? What does it mean that this is true? Who confirmed it and how?* Answering those questions is what generates depth without padding.

---

## Channel Voice & Tone

- **Register:** measured, authoritative, third-person documentary. Never first-person drama. Never "I think" or "imagine you're standing there."
- **Tense:** present-tense for mechanisms and physical descriptions ("the boulders sit at angles that..."), past-tense for historical events ("in 1882, police searched...").
- **Sentence rhythm:** short declarative sentences for revelation beats. Longer compound sentences for geological/archaeological explanation. Never more than two consecutive long sentences.
- **No victim dramatisation:** do not build emotional scenes around named individuals' suffering. Name the person, state what happened, move to the mechanism or implication.
- **Mythbusting is the hook within the hook:** the channel's core promise is "the explanation most people accept is wrong or incomplete." Every video must have a moment where a popular belief is tested against the actual record.
- **Specificity over generality:** "a 2022 investigation by Cooktown historian Bev Shay" is correct. "Researchers have found" is not acceptable.

---

## Title Formula (inferred from transcript style and Apex performance data)

**Formula:** `[Specific place or mystery] + [What people believe] + [What was actually found / the twist]`

The title must:
1. Name or strongly imply a specific, concrete subject (a place, a structure, a person, an event)
2. Establish the received version that most people hold
3. Signal that what follows will update or overturn that version

**Worked examples:**
- ✅ "The Mountain in Queensland Where People Vanish — And What a Historian Found When She Actually Checked"
- ✅ "Britain Has a Roman Fort That Shouldn't Exist — Archaeologists Still Don't Agree on Why"
- ✅ "The English Village That Was Deliberately Erased from Maps — The Real Reason Was Hidden for Centuries"
- ❌ "Mysterious British History You Didn't Know" — too vague, no concrete subject
- ❌ "This Will Change How You Think About England" — no specificity, pure clickbait register
- ❌ "Top 10 Strange British Mysteries" — wrong format (this is single-topic, not countdown)

Every title must be instantly understandable with zero interpretation. If a viewer needs prior knowledge to understand what the video is about, the title has failed.

---

## Channel Positioning & Topic Rotation

Four content registers, rotated so no two consecutive videos use the same one:

1. **Lost / erased history** — places, people, or events deliberately suppressed, forgotten, or misattributed. The real story is recoverable but requires looking past the accepted version.
2. **Landscape mystery / physical danger** — locations with documented anomalies, disappearances, or physical hazards that have generated folklore. Scientific explanation is the payoff.
3. **Indigenous / pre-Roman knowledge** — ancient British or Celtic peoples who understood something about their landscape that later settlers ignored at cost. The knowledge was right; the dismissal of it was wrong.
4. **Institutional failure** — cases where official records, archaeological bodies, or government policy produced a false account that persisted. The correction came from outside the institution.

**Never repeat the same register two videos in a row.**

### Topic Rotation Log

Update after every new video generated. Format: `[Date] Title — Register — Notes`

- [Seed] — "Black Mountain" (Kalkajaka, QLD) — R2 — source transcript; Australian, used for calibration only
- [Next] — Use R1, R3, or R4 with proven title formula, full British subject

**When asked to "make new video":** pick the register not used in the last two entries, apply the title formula, write to 2,465+ words, log the new entry.

---

## Script Structure (beat by beat)

### Beat 1 — Hook (2–3 segments, ~250 words)

Open on a specific, concrete, visually grounded scene. No abstract thesis statement. The first sentence must place the viewer in a location or confront them with a fact they did not expect. The hook establishes a **resolvable curiosity gap** — the viewer must feel that the answer exists and that this video has it.

Segment 5 or 6: first subscribe CTA. **Must be `remotion:FactCard` with `layout: "overlay"`** — b-roll of the location continues underneath; a large popup asks viewers to subscribe. Do **not** use stock subscribe CTA footage.

### Beat 2 — Setting / Geography (2–3 segments, ~225 words)

Establish the physical reality of the subject. Geology, landscape, structure, scale. Use precise measurements and visual language. This beat builds credibility and grounds the mystery in the material world before the historical layer is added.

### Beat 3 — Indigenous / Ancient Knowledge (2–3 segments, ~230 words)

What did the people who lived here first understand about this place? This beat is not optional. Every Ancient Britain video must engage with pre-Roman, Celtic, or early medieval knowledge systems that intersect with the subject. Named sources, named scholars, named traditions where available. This is what separates the channel from amateur mystery content.

### Beat 4 — Colonial / Historical Record (3–4 segments, ~315 words)

Trace the documented history from earliest European record forward. Name specific years, names, and sources. Where the historical record is patchy, say so explicitly — the gap in the record is part of the story. Do not invent continuity.

### Beat 5 — Folklore / Mystery Layer (2–3 segments, ~225 words)

What stories grew up around this subject, and when? Trace the mythology explicitly — not to validate it, but to understand it as a cultural artefact. Where did it appear in print? Who amplified it? What emotional or social need did it serve?

### Beat 6 — Mid-video CTA (1 segment, ~70 words)

Placed just before the payoff. **Must be `remotion:FactCard` or `remotion:TitleCard` with `layout: "overlay"`** — not stock CTA footage. Acknowledge that the viewer is waiting for the explanation. Second subscribe ask. Tease that the real finding is more interesting than the supernatural version.

### Beat 7 — Scientific / Historical Investigation (3–4 segments, ~320 words)

The investigation that tested the received account. Name the researcher, the institution, the methodology, and the specific finding. This is the heart of the video. If a popular claim does not hold up to scrutiny, say so directly and explain why it spread anyway. If the real explanation is more complex than the simple debunk, give the complexity.

### Beat 8 — Real Explanation + Conclusion (2–3 segments, ~250 words)

The grounded explanation that accounts for everything. What actually happened and why. What the original indigenous or ancient knowledge got right that later accounts missed. End on the implication — not a moral, but a specific, true thing that the viewer now knows that they didn't know at the start.

### Beat 9 — Outro (1–2 segments, ~120 words)

Comment-bait question: specific, not generic. ("Had you heard this version of the story before, or the other one?") Subscribe ask. Tease next video topic (different register than current). Share ask tied to the specific insight just delivered, not a generic "share with your friends."

---

## What Makes a Beat Deep Enough

Every beat should contain all of:

1. **The claim** — what is being established
2. **The evidence** — specific source, date, name, measurement
3. **The mechanism** — why this is true, how it works physically or historically
4. **The implication** — what this means for the story, the place, or the viewer

If any of these four layers is missing from a beat, the beat is not finished. Depth comes from mechanism and implication, not from adding more claims.

---

## Research Workflow

1. Web-search real dates, names, and primary sources before writing every script. Cross-reference at least two sources for any specific claim.
2. Where a popular account differs from primary records, flag the discrepancy explicitly in the script — this mythbusting moment is a core retention device.
3. Identify named researchers, historians, or archaeologists associated with the subject. Named sources increase credibility and distinguish the channel from content farms.
4. Do not pick the most dramatic version of an uncertain figure. Flag the range and use the documented one.
5. For British subjects: check Historic England, the Portable Antiquities Scheme, English Heritage records, the British Museum online catalogue, and regional archaeology journals as primary source pools.

---

## Remotion vs Stock Placement Rules

| Content type | Segment type | Layout |
|---|---|---|
| Subscribe CTA (hook or mid-video) | `remotion:FactCard` | **`overlay`** — never stock CTA footage |
| Quick fact, date, name, statistic while narration continues | `remotion:FactCard` | **`overlay`** (default) |
| Dense numbered list, warning checklist | `remotion:FactCard` | `split-right` |
| Chapter title, new beat opening | `remotion:TitleCard` | `full` |
| Atmospheric narration, landscape, process | `stock` or `commons` b-roll only | — |
| Historical event with no available footage | `commons` archival or `stock` reconstruction | — |

### Layout decision tree

1. **Is it a subscribe or channel CTA?** → `overlay` Remotion popup. B-roll = relevant location footage underneath.
2. **Is it a short fact (≤ 3 lines on screen)?** → `overlay` popup while b-roll plays.
3. **Is it a long bullet list (4+ items)?** → `split-right` FactCard.
4. **Is it a chapter break with no b-roll?** → `full` TitleCard.
5. **Everything else atmospheric** → plain `stock` / `commons` segment.

### Overlay popup rules

- Set `remotion.layout` to `"overlay"`.
- Set `remotion.overlay.position` to one of: `"lower-third"` (default, best for CTAs), `"center"` (revelations, named discoveries), `"top-banner"` (chapter labels, dates).
- The `description` field names the **full-frame b-roll** playing underneath (same as split-screen left panel).
- Include `remotion.broll` with `search_query` and `category` when the script source is explicit — the pipeline uses this for fetch.
- Popup copy must be **short and huge** — viewers should read it in under 2 seconds. Title + 1–2 lines max for CTAs; title + 3 bullets max for info popups.

### Split-screen rules

- FactCard renders on the right half. B-roll plays on the left.
- Use only when the on-screen list is too long for a popup panel.

### Ratio target

**6–10 Remotion segments per episode**, mixed across layouts:

- 2 overlay CTAs (hook + mid-video) — mandatory
- 2–4 overlay info popups (dates, names, key facts)
- 1–2 split-right FactCards (dense lists)
- 1–2 full TitleCards (chapter breaks)

Do not make every segment Remotion. Atmospheric stock/commons segments are still the backbone (~60–65% of runtime).

---

## Channel Design System

All Remotion segments default to this design system unless the beat demands an override.

**Color palette:**
- Background: deep charcoal radial gradient, `#1a1a1a` to `#2e2e2e` (near-black, not pure black)
- Title text: off-white `#f0ede8` (warm, not clinical)
- Body/bullet text: muted warm grey `#b8b3ab`
- Accent: deep British heritage red `#8b1a1a` (used for badge, bullet dots, accent bar — never for background)
- Badge background: `#8b1a1a` at 90% opacity

**Typography (mandatory — fill the frame):**

Text must be **large, legible on a TV/phone, and use most of the available card area**. Small type is an error. When in doubt, go bigger.

- **Primary font:** [Special Elite](https://fonts.google.com/specimen/Special+Elite) — `"Special Elite", Georgia, serif"`
- **Title weight:** 400 (Special Elite is a single-weight display face; do not use 700)
- **Line height:** 1.45 for body, 1.15 for title
- **Text align:** left for FactCard, center for TitleCard

**Size floors (never go below these):**

| Composition | Layout | `titleSize` | `bodySize` / `subtitleSize` | `labelSize` | `contentMaxWidth` | `padding` |
|---|---|---:|---:|---:|---:|---:|
| FactCard | overlay popup | **80** | **48** | **30** | **1600** | **40** |
| FactCard | split-right (960px panel) | **96** | **52** | **32** | **900** | **36** |
| FactCard | full frame | **110** | **56** | **34** | **1700** | **64** |
| TitleCard | full frame | **120** | **56** | — | **1700** | **72** |
| TitleCard | overlay popup | **88** | **48** | — | **1600** | **40** |

**Space rules:**
- **Overlay popups** render on a wide lower-third or center panel over full-frame b-roll. Text must dominate the popup — not float small inside a huge dark box.
- **Split-right** FactCards render in a **960×1080** panel. Set `contentMaxWidth` to **900** so text spans nearly the full right half.
- **Full-frame** cards should feel poster-sized. Title at 110–120px is normal, not excessive.
- Keep `padding` tight. Do not pad so much that the type shrinks visually.
- Limit on-screen copy: short title (≤ 8 words), body as 1–4 bullet lines max. Fewer words → bump sizes toward the top of the range.
- Every Remotion `props`, `design.typography`, and `prompt` must cite **Special Elite** and the numeric sizes above.

**Motion personality:** calm and deliberate. No kinetic energy. Spring fade-up on enter (~0.5s, 40px travel). Badge enters first (8 frames), then title (8 frames), then body (12 frames). No zoom. No bounce. Hold through full narration. Soft cut to b-roll after.

**TitleCard specifics:** centered layout, large title, subtitle below, thin accent bar beneath title (heritage red), no badge. Background same charcoal gradient.

---

## script.json Schema

```json
{
  "title": "string",
  "channel": "Ancient Britain",
  "script": [
    {
      "beat": 1,
      "label": "string — beat name",
      "segments": [
        {
          "segment_id": 1,
          "content": "narration — target 85–110 words per segment",
          "description": "plain-language visual for editor / left-side b-roll if Remotion",
          "type": ["search query string", "stock | commons"]
        }
      ]
    }
  ]
}
```

### Required top-level structure

- The deliverable must be a JSON object with a top-level `script` array.
- Do **not** use a top-level `segments` array.
- Every item in `script` must be a beat block:
  - `beat`: integer
  - `label`: short beat name
  - `segments`: array of segment objects

### Stock / commons segment rules

- `type` is always a 2-element array: `[search_query, category]`
- `search_query`: plain English, pasteable into Storyblocks or Wikimedia Commons. Specific and visual.
- `category`: `"stock"` for Storyblocks / commercial footage; `"commons"` for Wikimedia Commons / public domain archival
- Do **not** use `"type": "broll"`. That is invalid for this pipeline.
- **Identical strings every recurrence** — character-for-character. `"granite boulder field aerial"` must appear as `"granite boulder field aerial"` every time it is used. No phrasing drift.
- Reuse connective-tissue queries across beats: `"narrator documentary British landscape"`, `"historical archive map parchment"`, `"aerial countryside England"`.

### Remotion segment rules

Supported `remotion.layout` values: `"overlay"`, `"split-right"`, `"full"`.

**Overlay popup (default for CTAs and short facts):**

```json
{
  "segment_id": 5,
  "content": "This channel covers the British history most people were never properly taught. If that's your kind of thing, subscribe now.",
  "description": "Wide aerial of the subject landscape — b-roll plays full frame underneath popup",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "overlay",
    "overlay": {
      "position": "lower-third"
    },
    "broll": {
      "search_query": "aerial countryside England misty morning",
      "category": "stock"
    },
    "props": {
      "title": "Subscribe for the Real History",
      "body": "British places and stories behind the postcard version",
      "factNumber": null,
      "showFactBadge": false,
      "accentColor": "#8b1a1a",
      "textColor": "#f0ede8",
      "bodyColor": "#b8b3ab",
      "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
      "fontFamily": "Special Elite, Georgia, serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 40,
      "contentMaxWidth": 1600,
      "titleSize": 80,
      "bodySize": 48,
      "titleWeight": 400,
      "lineHeight": 1.45
    },
    "design": {
      "intent": "Hook subscribe CTA — large popup over landscape b-roll, not stock CTA footage",
      "layout": {
        "mode": "overlay",
        "position": "lower-third",
        "textAlign": "left",
        "verticalAlign": "center",
        "hierarchy": "title dominant, one-line body secondary",
        "contentMaxWidth": "wide lower-third popup panel over full-frame b-roll"
      },
      "typography": {
        "titleFont": "Special Elite",
        "bodyFont": "Special Elite",
        "titleSize": "80px",
        "bodySize": "48px",
        "titleWeight": 400,
        "lineHeight": 1.45
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
        "text": "#f0ede8",
        "body": "#b8b3ab",
        "accent": "#8b1a1a",
        "accentUsage": "optional thin accent bar only"
      },
      "motion": {
        "enter": "spring fade-up 40px, ~0.5s, calm",
        "exit": "popup fades as narration continues over b-roll",
        "stagger": "title +8 frames → body +16 frames",
        "emphasis": "none",
        "easing": "spring"
      },
      "overlays": {
        "badge": "none for CTA popups",
        "decorations": "subtle vignette on popup panel edges only — b-roll stays visible around it",
        "iconography": "none"
      },
      "transitions": {
        "in": "popup rises over continuing b-roll",
        "out": "soft fade, b-roll holds"
      },
      "durationHint": "hold through CTA narration line"
    },
    "prompt": "Full-frame aerial b-roll of misty British countryside plays underneath. Large lower-third Remotion popup panel (Special Elite, 80px title, 48px body) rises over the footage — not a stock subscribe graphic. Title 'Subscribe for the Real History' in off-white (#f0ede8), one body line below in muted grey (#b8b3ab). Deep charcoal popup background (#2e2e2e to #1a1a1a). B-roll remains visible above and around the panel. Spring fade-up enter. No badge. Hold through CTA line then fade popup while b-roll continues."
  }
}
```

**Split-right FactCard (dense lists):**

```json
{
  "segment_id": 7,
  "content": "narration — what the voiceover says during this card",
  "description": "b-roll for left side of split-screen",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "split-right",
    "props": {
      "title": "string — card headline",
      "body": "string — bullet list or short paragraph shown on card",
      "factNumber": null,
      "showFactBadge": true,
      "accentColor": "#8b1a1a",
      "textColor": "#f0ede8",
      "bodyColor": "#b8b3ab",
      "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
      "fontFamily": "Special Elite, Georgia, serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 36,
      "contentMaxWidth": 900,
      "titleSize": 96,
      "bodySize": 52,
      "labelSize": 32,
      "titleWeight": 400,
      "lineHeight": 1.45
    },
    "design": {
      "intent": "one sentence — on-screen purpose and mood",
      "layout": {
        "textAlign": "left",
        "verticalAlign": "center",
        "hierarchy": "title dominant, body secondary, badge tertiary",
        "contentMaxWidth": "right half of split-screen frame, 900px — nearly full panel width"
      },
      "typography": {
        "titleFont": "Special Elite",
        "bodyFont": "Special Elite",
        "titleSize": "96px",
        "bodySize": "52px",
        "titleWeight": 400,
        "lineHeight": 1.45
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
        "text": "#f0ede8",
        "body": "#b8b3ab",
        "accent": "#8b1a1a",
        "accentUsage": "badge background, bullet dot markers"
      },
      "motion": {
        "enter": "spring fade-up 40px, ~0.5s, calm",
        "exit": "soft cut to b-roll",
        "stagger": "badge 0ms → title +8 frames → body +20 frames",
        "emphasis": "none — no word-level animation",
        "easing": "spring"
      },
      "overlays": {
        "badge": "chapter label or fact label — heritage red pill",
        "decorations": "subtle vignette on card edges, no grain",
        "iconography": "none"
      },
      "transitions": {
        "in": "fade from previous b-roll, card slides up from 40px below",
        "out": "soft cut to next b-roll segment"
      },
      "durationHint": "hold for full narration beat"
    },
    "prompt": "string — self-contained paragraph describing everything: background gradient, layout, fonts, colors, motion, badge, overlays, transitions, and mood. No references to other segments. Must be pasteable standalone."
  }
}
```

**TitleCard props** (when used for beat openings):

```json
{
  "composition": "TitleCard",
  "props": {
    "title": "string",
    "subtitle": "string",
    "showAccentBar": true,
    "accentColor": "#8b1a1a",
    "textColor": "#f0ede8",
    "subtitleColor": "#b8b3ab",
    "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
    "fontFamily": "Special Elite, Georgia, serif",
    "textAlign": "center",
    "verticalAlign": "center",
    "padding": 72,
    "contentMaxWidth": 1700,
    "titleSize": 120,
    "subtitleSize": 56,
    "titleWeight": 400,
    "lineHeight": 1.15
  }
}
```

`props`, `design`, and `prompt` must be **consistent**. If they conflict, fix before delivering.

### Remotion compatibility rules

- Use only supported compositions: `FactCard`, `TitleCard`
- Use only supported layouts: `overlay`, `split-right`, `full`
- Put layout on `remotion.layout`, **not** inside `remotion.props`
- Put popup position on `remotion.overlay.position` (`lower-third`, `center`, `top-banner`)
- **Never use stock footage for subscribe CTAs** — always `remotion` with `layout: "overlay"`
- Use `body`, **not** `bullets`
- Use `bodyColor`, **not** `bulletColor`
- Use numeric values for size/layout props (`96`, `52`, `900`), **not** pixel strings like `"48px"`
- **Typography is non-negotiable:** always use `"Special Elite, Georgia, serif"` and meet the size floors in Channel Design System.
- Overlay FactCard: `titleSize` ≥ 80, `bodySize` ≥ 48. Split-right: `titleSize` ≥ 96, `bodySize` ≥ 52. Full TitleCard: `titleSize` ≥ 120.
- Set `contentMaxWidth` to **900** for split-right, **1600+** for overlay popups.
- Do not invent custom render props like `badgeText` unless they are duplicated safely in `design` / `prompt` only
- If you want bullet-style text on screen, encode it inside `props.body` as newline-separated bullet text

---

## Worked Examples

### Example A — Stock segment

```json
{
  "segment_id": 4,
  "content": "The boulders themselves are not actually black. Most granite of this type is naturally pale grey. The colour comes from a thin biological crust — a combination of lichen and algae that has grown across the surface over an enormous span of time, darkening it to the deep charcoal that gives the formation its name. Up close, the rock underneath is the same pale granite found across the wider landscape. The darkness is entirely surface-deep.",
  "description": "Close-up of dark granite rock surface showing lichen growth, then pull back to reveal pale grey rock beneath where crust has flaked away",
  "type": ["granite boulder lichen close up", "stock"]
}
```

### Example B — FactCard segment (split-screen)

```json
{
  "segment_id": 9,
  "content": "Park authorities ask visitors to observe the formation only from designated lookout points on the surrounding road. There is no marked trail into the boulder field, no safety barrier installed partway up, and no rescue infrastructure built into the rock itself. These are not arbitrary rules. The terrain genuinely cannot support any of them.",
  "description": "Left side b-roll: wide shot of closed gate or lookout point with rocky formation visible in background",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "split-right",
    "props": {
      "title": "Infrastructure Missing",
      "body": "• No marked trail into the boulder field\n• No safety barrier installed partway\n• No rescue infrastructure built in",
      "factNumber": null,
      "showFactBadge": true,
      "accentColor": "#8b1a1a",
      "textColor": "#f0ede8",
      "bodyColor": "#b8b3ab",
      "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
      "fontFamily": "Special Elite, Georgia, serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 36,
      "contentMaxWidth": 900,
      "titleSize": 96,
      "bodySize": 52,
      "labelSize": 32,
      "titleWeight": 400,
      "lineHeight": 1.45
    },
    "design": {
      "intent": "Anchor the viewer to the physical reality that no safety infrastructure exists — this is not neglect but genuine impossibility. Calm, factual, slightly ominous.",
      "layout": {
        "textAlign": "left",
        "verticalAlign": "center",
        "hierarchy": "Title dominant. Three-bullet body secondary. Heritage red badge tertiary.",
        "contentMaxWidth": "Right half of split-screen, 900px — text spans nearly full panel"
      },
      "typography": {
        "titleFont": "Special Elite",
        "bodyFont": "Special Elite",
        "titleSize": "96px",
        "bodySize": "52px",
        "titleWeight": 400,
        "lineHeight": 1.45
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
        "text": "#f0ede8",
        "body": "#b8b3ab",
        "accent": "#8b1a1a",
        "accentUsage": "Heritage red badge pill, bullet dot markers"
      },
      "motion": {
        "enter": "spring fade-up 40px, ~0.5s, calm",
        "exit": "soft cut to b-roll",
        "stagger": "badge 0ms → title +8 frames → bullet 1 +20 frames → bullets 2–3 +6 frames each",
        "emphasis": "none",
        "easing": "spring"
      },
      "overlays": {
        "badge": "Warning — heritage red pill, top-left",
        "decorations": "subtle vignette on card edges only",
        "iconography": "none"
      },
      "transitions": {
        "in": "fade from b-roll, card rises from 40px below",
        "out": "soft cut to location b-roll"
      },
      "durationHint": "hold through full narration — approximately 20 seconds"
    },
    "prompt": "Deep charcoal radial gradient background (#2e2e2e to #1a1a1a). Right-half split-screen layout — b-roll footage of a closed gate with rocky formation visible plays on the left; this card occupies the right 960px panel. Left-aligned text, vertically centered, content spanning ~900px width. Very large Special Elite title 'Infrastructure Missing' in off-white (#f0ede8), 96px, weight 400. Three bullet points below in muted warm grey (#b8b3ab), 52px Special Elite, line height 1.45. Heritage red badge pill (#8b1a1a) top-left labelled 'Warning', 32px. Spring fade-up enter animation over ~0.5 seconds: badge appears first, title rises 8 frames later, bullets stagger 6 frames apart. No zoom. No bounce. Subtle edge vignette on card only. Hold through full narration (~20 seconds). Soft cut to location b-roll after."
  }
}
```

### Example C — TitleCard segment (beat opening)

```json
{
  "segment_id": 12,
  "content": "What the historian actually found.",
  "description": "Full-frame TitleCard — transition beat before the investigation payoff",
  "type": "remotion:TitleCard",
  "remotion": {
    "composition": "TitleCard",
    "layout": "full",
    "props": {
      "title": "What the Historian Found",
      "subtitle": "Testing 150 years of stories against the actual record",
      "showAccentBar": true,
      "accentColor": "#8b1a1a",
      "textColor": "#f0ede8",
      "subtitleColor": "#b8b3ab",
      "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
      "fontFamily": "Special Elite, Georgia, serif",
      "textAlign": "center",
      "verticalAlign": "center",
      "padding": 72,
      "contentMaxWidth": 1700,
      "titleSize": 120,
      "subtitleSize": 56,
      "titleWeight": 400,
      "lineHeight": 1.15
    },
    "design": {
      "intent": "Chapter-break card signalling the shift from mystery-building to evidence-testing. Tone: calm authority, not dramatic reveal.",
      "layout": {
        "textAlign": "center",
        "verticalAlign": "center",
        "hierarchy": "Title dominant, thin accent bar below title, subtitle tertiary",
        "contentMaxWidth": "1700px centered on full frame — title fills the width"
      },
      "typography": {
        "titleFont": "Special Elite",
        "bodyFont": "Special Elite",
        "titleSize": "120px",
        "bodySize": "56px",
        "titleWeight": 400,
        "lineHeight": 1.15
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
        "text": "#f0ede8",
        "body": "#b8b3ab",
        "accent": "#8b1a1a",
        "accentUsage": "Thin horizontal bar beneath title, 3px height"
      },
      "motion": {
        "enter": "spring fade-up 40px, ~0.6s",
        "exit": "soft fade to b-roll",
        "stagger": "title → accent bar +8 frames → subtitle +16 frames",
        "emphasis": "none",
        "easing": "spring"
      },
      "overlays": {
        "badge": "none",
        "decorations": "no grain, no vignette — clean card",
        "iconography": "none"
      },
      "transitions": {
        "in": "fade from previous b-roll segment",
        "out": "soft fade to researcher b-roll"
      },
      "durationHint": "hold 4–5 seconds, enough for narration line plus a breath"
    },
    "prompt": "Full-frame deep charcoal radial gradient (#2e2e2e to #1a1a1a). Centered layout, content max-width 1700px. Poster-sized Special Elite title 'What the Historian Found' in off-white (#f0ede8), 120px, weight 400, centered horizontally and vertically — title should dominate the frame. Thin heritage red horizontal rule (#8b1a1a, 3px) immediately beneath the title. Subtitle 'Testing 150 years of stories against the actual record' below the rule in muted warm grey (#b8b3ab), 56px Special Elite, weight 400. Spring fade-up enter over ~0.6s: title rises first, accent bar appears 8 frames later, subtitle fades in 16 frames after that. No badge. No grain. No vignette. Clean card. Hold 4–5 seconds. Soft fade to b-roll showing researcher or archive footage."
  }
}
```

### Example D — Overlay info popup (date / fact over b-roll)

```json
{
  "segment_id": 14,
  "content": "Radiocarbon dating places the main occupation phase between roughly 3180 and 2500 BC — nearly six hundred continuous years on the same site.",
  "description": "Archaeological dig site, researchers working in trenches — full-frame b-roll underneath",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "overlay",
    "overlay": { "position": "center" },
    "broll": {
      "search_query": "archaeological excavation trench workers",
      "category": "stock"
    },
    "props": {
      "title": "3180–2500 BC",
      "body": "Nearly 600 years of continuous occupation",
      "showFactBadge": true,
      "accentColor": "#8b1a1a",
      "textColor": "#f0ede8",
      "bodyColor": "#b8b3ab",
      "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
      "fontFamily": "Special Elite, Georgia, serif",
      "textAlign": "center",
      "verticalAlign": "center",
      "padding": 40,
      "contentMaxWidth": 1600,
      "titleSize": 88,
      "bodySize": 48,
      "labelSize": 30,
      "titleWeight": 400,
      "lineHeight": 1.45
    },
    "design": {
      "intent": "Anchor the date range while dig b-roll continues — viewer reads the span instantly",
      "layout": {
        "mode": "overlay",
        "position": "center",
        "hierarchy": "date title dominant, one-line context secondary"
      },
      "typography": {
        "titleFont": "Special Elite",
        "bodyFont": "Special Elite",
        "titleSize": "88px",
        "bodySize": "48px",
        "titleWeight": 400,
        "lineHeight": 1.45
      },
      "motion": {
        "enter": "spring fade-up, calm",
        "exit": "fade while b-roll holds"
      }
    },
    "prompt": "Full-frame excavation b-roll underneath. Centered overlay popup with huge Special Elite date range '3180–2500 BC' at 88px and one context line at 48px. B-roll stays visible around the panel. Heritage red badge 'The Dates'. Spring fade-up enter. Hold through narration line."
  }
}
```

### Example E — Overlay subscribe CTA (mid-video)

```json
{
  "segment_id": 23,
  "content": "If you're enjoying this one, subscribe — the real explanation for what happened here is stranger and slower than any single storm.",
  "description": "Wide landscape of the subject location — atmospheric b-roll full frame",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "overlay",
    "overlay": { "position": "lower-third" },
    "broll": {
      "search_query": "aerial British landscape coastline mist",
      "category": "stock"
    },
    "props": {
      "title": "Subscribe Before the Payoff",
      "body": "The real story is more interesting than the myth",
      "showFactBadge": false,
      "accentColor": "#8b1a1a",
      "textColor": "#f0ede8",
      "bodyColor": "#b8b3ab",
      "backgroundGradient": "radial-gradient(ellipse at center, #2e2e2e 0%, #1a1a1a 100%)",
      "fontFamily": "Special Elite, Georgia, serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 40,
      "contentMaxWidth": 1600,
      "titleSize": 80,
      "bodySize": 48,
      "titleWeight": 400,
      "lineHeight": 1.45
    },
    "prompt": "Mid-video subscribe moment. Full-frame misty British landscape b-roll continues underneath. Large lower-third popup — NOT stock subscribe footage. Special Elite 80px title, 48px body line. Popup rises over b-roll, holds through CTA, fades while landscape continues."
  }
}
```

---

## Validation Checklist (mandatory before delivering)

Run all of these silently before presenting the file:

1. **JSON validity** — parse the file. Fail = fix before delivering. Do not deliver malformed JSON.
2. **Word count** — sum all `content` fields. Must be ≥ 2,400 words. Divide by 145 and report runtime in minutes. If under 16 minutes, do not deliver — expand beats.
3. **Per-beat completeness** — every beat from the structure table must be present. Flag and add any missing beats.
4. **Segment word count** — target 85–110 words per segment. Flag segments under 70 words and expand unless they are CTA or transitional segments.
5. **Type-field consistency** — group all `type[0]` strings and confirm identical string and category on every recurrence. Fix near-duplicates.
6. **Title check** — confirm title follows formula: specific subject + received version + implied twist. No vague titles.
7. **Remotion segment audit** — every Remotion segment must have: `composition`, `layout`, complete `props`, complete `design`, non-empty `prompt`. Overlay/split segments must have b-roll described in `description` (and `remotion.broll` when explicit). `props`, `design`, and `prompt` must be internally consistent.
8. **Remotion count** — 6–10 Remotion segments per episode (mix of overlay, split-right, full). Fewer than 6 = under-visualized. More than 12 = error.
9. **CTA check** — both subscribe CTAs (hook + mid-video) must be `remotion` with `layout: "overlay"`. No stock subscribe CTA segments.
10. **Schema check** — top-level object contains `script`, not `segments`.
11. **Stock type check** — every non-Remotion segment uses `type: [search_query, category]`; no `"broll"` strings.
12. **Typography check** — every Remotion segment uses `"Special Elite, Georgia, serif"`, meets size floors, and `props` / `design` / `prompt` all agree.
13. **Layout mix check** — episode includes at least 2 overlay CTAs, 2+ overlay info popups, and no more than 3 split-right cards unless justified by long lists.
14. **Update Topic Rotation Log** with the new entry.

---

## Efficiency Note

Write complete files in a single pass. When the user says "make new video," proceed immediately — apply register rotation and title formula automatically, research real facts via web search, and deliver `script.json`. Do not ask clarifying questions when this skill's rules already provide the answer.