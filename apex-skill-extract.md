---
name: apex-archives-script-writer
description: Use this skill whenever the user wants to write, plan, or expand a video script or title for "Apex Archives," a YouTube channel about dangerous/extreme-biology animal documentaries. Trigger this for requests to generate countdown/ranking scripts, single-animal deep-dive scripts, title brainstorming, broll search-term JSON for this channel, or when the user says "make new video." Also trigger if the user references "Apex Archives" or asks to continue/expand a previous Apex Archives script.
---

# Apex Archives Script Writer

A skill for producing `script.json` files for **Apex Archives**, a YouTube channel making ~58-minute narrated documentary-style countdown videos about animals, biology, and danger. This file encodes channel strategy, real performance data, the title/hook formula, script voice/structure, Remotion composition rules, the full `script.json` schema, validation checklist, and a topic-rotation system so new videos don't repeat old angles.

Read this whole file before starting any new Apex Archives task.

---

## REMOTION SYSTEM — READ THIS FIRST

Every script now ships as a full Remotion-aware `script.json`. Remotion segments are **rendered video graphics, not just editor notes** — subscribe CTAs, rank reveals, quick stat popups, and comparison lists are built as on-screen animated cards over or instead of b-roll. Stock/commons b-roll remains the backbone of the video (~75-80% of runtime); Remotion carries the moments that need to be read, not just watched.

**Remotion layouts supported:**

1. **`overlay`** — full-frame b-roll continues underneath, with a large popup on top (lower-third, center, or top-banner). Use for subscribe CTAs, retention teases, quick stats, and single-line revelations.
2. **`split-right`** — b-roll plays on the left half, a full FactCard panel on the right half. Use for comparative lists, ranked stat breakdowns, or anything with 3+ bullet points.
3. **`full`** — the entire frame is Remotion. This is mandatory for every **entry rank reveal** (the "#7: Golden Poison Frog" moment that opens each countdown entry) and for major chapter breaks (methodology beat, final countdown stretch).

**Never fetch stock "subscribe" or "like and subscribe" footage.** Every subscribe CTA, like-and-subscribe popup, and rank reveal is a Remotion composition — no exceptions.

---

## RUNTIME TARGET — READ THIS FIRST

**Target: 58 minutes at 145 words per minute = 8,410 words minimum.**

This is a hard requirement. Do not deliver a script under 8,000 words. Do not assume the target has been hit — compute it explicitly before delivering.

### Why scripts keep coming in short and how to fix it

Analysis of a generated script that came in at 32.9 minutes revealed the root cause:
- Average segment length: **68 words** (needs to be ~120 words)
- Average segments per entry: **5** (needs to be **10-11**)
- Average minutes per entry: **2.4 min** (needs to be **~5 min**)

**Every numbered countdown entry must be 10-11 segments and ~700-800 words minimum.** That is the single most important rule in this file. If an entry is shorter than 700 words, it is not deep enough — add more mechanism detail, comparative context, geographic specificity, scientific nuance, or consequence framing until it reaches that threshold. Do not pad with filler; deepen with real content.

### Target structure for a 10-entry 58-minute video

| Section | Segments | Words | Minutes | Remotion |
|---|---|---|---|---|
| Hook | 7-8 | 450 | 3.1 | 1 overlay CTA (~seg 5-6) |
| Methodology beat | 3-4 | 220 | 1.5 | 1 full TitleCard (chapter open) |
| Entry #10 | 10-11 | 750 | 5.2 | 1 full rank reveal + 0-1 overlay stat |
| Entry #9 | 10-11 | 750 | 5.2 | 1 full rank reveal + 0-1 overlay stat |
| Retention tease 1 | 1-2 | 100 | 0.7 | 1 overlay popup |
| Entry #8 | 10-11 | 750 | 5.2 | 1 full rank reveal |
| Entry #7 | 10-11 | 750 | 5.2 | 1 full rank reveal + 0-1 overlay/split stat |
| Entry #6 | 10-11 | 750 | 5.2 | 1 full rank reveal |
| Retention tease 2 | 1-2 | 100 | 0.7 | 1 overlay popup |
| Entry #5 | 10-11 | 750 | 5.2 | 1 full rank reveal + 0-1 split-right comparison |
| Entry #4 | 10-11 | 750 | 5.2 | 1 full rank reveal |
| Entry #3 | 10-11 | 750 | 5.2 | 1 full rank reveal + 0-1 overlay stat |
| Final tease | 1 | 80 | 0.6 | 1 overlay popup |
| Entry #2 | 10-11 | 750 | 5.2 | 1 full rank reveal |
| Entry #1 | 12-14 | 900 | 6.2 | 1 full rank reveal (largest treatment) + 1 overlay stat |
| Outro | 5-6 | 320 | 2.2 | 1 overlay like/subscribe popup |
| **TOTAL** | **~125-130** | **~8,620** | **~59.4** | **~22-28 Remotion segments (~18-22% of segments)** |

---

## Critical Performance Data (real channel analytics — do not ignore)

**Length is locked at ~58 minutes.** Every video at this length got 12-20K impressions and 29-33% AVD. Videos at 15, 32, and 34 minutes got under 100 impressions each — YouTube appears to have stopped testing them almost immediately, likely because they break the channel's established length identity. **Never deliver under 8,000 words.**

**The real bottleneck is impressions, not just CTR.** Analyzed side-by-side, winning and losing videos often have *comparable* CTR — one flop ("These Animals Have Already Invaded Your Country") actually hit 6.5% CTR, higher than any winner, but on only 217 total impressions. The pattern: winners got 14,000-20,000 impressions; flops got 200-600. YouTube tests every new video on a small initial sample; if that sample's early signals look weak, it simply stops expanding distribution rather than waiting for the video to "catch up." This means a video's fate is often decided in its first few hundred impressions — title and thumbnail have to win immediately, and format consistency (length, register, title formula) matters because it's what lets YouTube's small early sample generalize into a bigger push.

**Retention plateaus at ~27-35% regardless of runtime.** This holds true from a 15-minute video up to a 1:14:55 video — viewers watch roughly the same absolute number of minutes (15-24 min) no matter how long the video is. This means going longer than ~58 minutes does not buy proportionally more watch time, and it also means pacing/mechanism-depth in the first 20-25 minutes matters more than total length. Do not use "make it longer" as a fix for weak retention — fix pacing and hook strength in the early entries instead.

**Narration speed is 145 wpm** (confirmed from actual uploaded audio). Use this, not 150 wpm, for all runtime calculations.

**Proven title formula:** concrete named comparison + personal stakes + zero ambiguity.
- ✅ "This Animal Kills More People Than Sharks and Lions Combined (And It's Probably Near You)" → 726 views, 14.4k impressions, 4.1% CTR
- ✅ "These 'Safe' Animals Are Quietly Killing More People Than Most Wild Predators" → 1,290 views, 20.2k impressions, 4.9% CTR (best performer to date)
- ✅ "Ranking Every Deadly Animal in Africa" → 703 views, 17.9k impressions, 3.1% CTR
- ⚠️ "The Deer In Your Backyard Has Killed More Americans Than Sharks, Bears And Wolves" → 125 views, only 2.0k impressions despite following the formula — title formula alone doesn't guarantee a big initial test batch; deer as a subject may read as lower-stakes/less exotic than the channel's usual animals
- ❌ "These Animals Have Already Invaded Your Country" → 15 views, 217 impressions (too abstract, no concrete stake)
- ❌ "5 Animals That Look Beautiful But Will Kill You" → 12 views (too clever, wrong length — 15:43)
- ❌ "The Pet You Trust Carries More Risk Than You Know" → 20 views, only 496 impressions (abstract, no named stake, and ran 1:14:55 — too long)
- ❌ "These Animals Cannot Be Killed — Scientists Have Tried Everything" → 145-154 views, 2.5k impressions but only 33.2% retention and ran short at 32:30
- ❌ "The Venom That Kills You Is Also Saving Lives" → 16 views, 605 impressions, weak 1.7% CTR — dual-message titles (danger + benefit) appear to blunt the curiosity gap

Every title must: (1) name or strongly imply a concrete specific stake, (2) make it personal to the viewer, (3) be instantly understandable with zero interpretation required.

**Upload cadence:** every other day. Not daily — daily posting cannibalizes each video's testing window.

---

## Thumbnail Strategy

Thumbnail generation prompts are **not** part of this skill file — they live in a separate, standalone meta-prompt (ask for "the Apex Archives thumbnail prompt generator" or similar; it is not stored here per the channel owner's instruction). This section covers only which thumbnail *styles* to reach for and why, so the right style gets requested.

Based on vidIQ's research into high-CTR thumbnail formats, cross-referenced against this channel's own performance data, three formats consistently fit Apex Archives:

1. **Facts & Stats** — a bold number or comparison on screen (bite force in PSI, death toll, LD50). This is the direct visual equivalent of the channel's #1 proven title formula ("kills more than X combined") and should be the default thumbnail approach for stat-shock register (R1) videos.
2. **'Versus' Comparison** — two animals, or one animal against a human-scale reference, framed side by side. Maps directly onto comparative titles and R1/R3 videos.
3. **High-energy action shot / stunning wildlife image** — a single dramatic, high-contrast animal in the moment of striking, camouflaging, or displaying its danger. Best for R2 (perception-vs-reality) and R4 (wonder/capability) registers where there's no clean numeric hook to put on screen.

Formats that do **not** fit this channel and should not be requested: close-up human reaction faces, humor/satire, before-and-after, featured product, tutorial/how-to, emotional moments. This channel has no on-camera host and is not a tutorial or lifestyle channel — reaction-face and humor formats would break brand identity.

**Non-negotiable thumbnail rules regardless of format chosen:**
- Text on the thumbnail itself: **3-4 words maximum**. Full stat sentences belong in the title, not the image.
- **One clear focal point** — a single animal, a single number, a single face-off. Never multiple competing subjects.
- **High contrast** — bright subject against the channel's signature warm-black background, checked against both YouTube's light and dark mode.
- **Thumbnail and title work as a team, not a repeat** — the thumbnail creates the curiosity gap; the title resolves *what* it's about. Don't caption the thumbnail with the exact title text.
- Always generate **2-3 variants** per video for YouTube's built-in A/B thumbnail test — this channel already runs A/B tests on most uploads (see analytics notes), so variants should differ meaningfully (different format, not just a color swap).

---

## Channel Positioning & Topic Rotation

Four emotional registers, rotated so no two consecutive videos use the same one:

1. **Personal danger / stat-shock** — "kills more than X combined," lethality rankings, proximity fear. Proven best performer.
2. **Perception-vs-reality / hidden danger** — looks harmless/beautiful, isn't. Needs re-test at full 58-min length.
3. **Systemic consequence** — invasive species, ecosystem collapse, scale of damage. Needs re-test with a stronger title.
4. **Wonder / capability-driven** — sensory abilities, survival adaptations, unkillable biology. Not yet fully tested.

**Never repeat the same register two videos in a row.**

### Topic Rotation Log

Update after every new video generated. Format: `[Date] Title — Register — Performance`

- Jun 19 — "This Animal Kills More People Than Sharks and Lions Combined" — R1 — 726 views, 14.4k impressions, 4.1% CTR ✅
- Jun 21 — "These 'Safe' Animals Are Quietly Killing More People Than Most Wild Predators" — R1 — 1,290 views, 20.2k impressions, 4.9% CTR ✅ (best to date)
- Jun 23 — "The Pet You Trust Carries More Risk Than You Know" — R1 variant (abstract title, 1:14:55 — too long) — 20 views, 496 impressions ❌
- Jun 25 — "Ranking Every Deadly Animal in Africa" — R1 — 703 views, 17.9k impressions, 3.1% CTR ✅
- Jun 27 — "5 Animals That Look Beautiful But Will Kill You" — R2 (wrong length, 15:43) — 12 views ❌
- Jun 29 — "These Animals Have Already Invaded Your Country" — R3 (abstract title, 34:29) — 15 views, 217 impressions ❌ (note: 6.5% CTR was actually strong — the failure was impressions/reach, not the click decision itself)
- Jun 30 — "The Deer In Your Backyard Has Killed More Americans Than Sharks, Bears and Wolves" — R1 — 125 views, 2.0k impressions, 4.7% CTR ⚠️ (followed the formula but got a small initial test batch — deer may read as a lower-stakes subject for this audience)
- Jul 2 — "These Animals Cannot Be Killed — Scientists Have Tried Everything" — R4 (32:30, short) — 145-154 views, 2.5k impressions, 33.2% retention ❌
- Jul 4 — "These Animals Are Harming People Who Had No Idea They Were Even Dangerous" — R2 — 115-120 views, 3.8k impressions, 2.3% CTR ❌ (weak CTR, title lacks a concrete named stake)
- Jul 6 — "The Venom That Kills You Is Also Saving Lives — Scientists Found Out How" — R4 — 16 views, 605 impressions, 1.7% CTR ❌ (dual danger+benefit message blunts the hook)
- Jul 8 — "These Animals Have Spread Diseases That Harms More Humans Than Every War In History Combined" — R1 — too new to score at last check
- Jul 12 — "These Fish Look Completely Harmless — They Kill More Swimmers Every Year Than Sharks Combined (And One Lives In Your Aquarium)" — R2 — generated batch, pending upload
- Jul 12 — "These Invasive Animals Have Already Cost America More Than Every Hurricane Season Combined — And They're Still Spreading" — R3 — generated batch, pending upload
- Jul 12 — "Ranking Animals With Senses So Extreme Scientists Still Can't Build Them — From Vision to Electrolocation" — R4 — generated batch, pending upload
- Jul 12 — "Ranking Every Animal That Kills More Americans Each Year Than Bears, Wolves, and Cougars Combined (The #1 Entry Is In Your Yard)" — R1 — generated batch, pending upload
- Jul 12 — "These Animals Have Spread Diseases That Killed More Humans Than Every War In History Combined" — R1 — generated batch, pending upload
- [Next] — Use R2 or R3 with the proven title formula (named concrete stake + personal stakes), full 58 min, and treat the subject/animal itself as part of the stakes check — exotic/unexpected animals so far outperform familiar ones (deer) even inside the same title formula

**When asked to "make new video":** pick a register not used in the last 2 videos, apply the proven title formula, write to 8,400+ words, log the new entry.

---

## Script Voice & Structure

- **Hook (first 2 sentences):** immediate, specific, resolvable curiosity gap. No scene-setting before the hook. This is the most important retention moment in the video.
- **Early subscribe CTA:** segment 5-6, right after the hook establishes the promise. **Must be `remotion:FactCard` with `layout: "overlay"`** — full-frame b-roll continues underneath; never stock subscribe footage.
- **Methodology beat:** 3-4 segments explaining the ranking logic. Builds credibility. Opens with a `remotion:TitleCard` (`layout: "full"`) chapter card.
- **Entry rank reveal:** every numbered entry opens with a **mandatory** `remotion:TitleCard` or `remotion:FactCard` at `layout: "full"` — huge rank number (`factNumber`) plus the animal's name. This is the single biggest visual beat of each entry; it must dominate the frame.
- **Retention teases:** one after entry #9 (tease entries #5 and #1), one after entry #6 (tease #1 specifically). Don't just say "more coming" — name what's coming and why it's worth staying for. **Must be `remotion:FactCard` with `layout: "overlay"`**.
- **Narration voice:** present-tense, in-the-moment for action/mechanism beats. Give every entry a mechanism, not just a stat. Short fragments during tension; longer sentences during explanation.
- **No dramatized named-victim incident storytelling** by default. Stats-and-mechanism focus throughout.
- **Outro:** comment-bait question (specific, not generic), invite viewer regional/personal context, subscribe ask, next video tease (different register than current), share ask tied to the specific insight just delivered. Final subscribe ask is a **Remotion overlay like/subscribe popup**, not stock footage.

---

## What Makes Entries Long Enough

The consistent failure mode is entries that cover what an animal does but not why, how, or what it means. Every entry should include all of:

1. **Introduction** — what the animal is, why it's on this list, what makes it unusual (1-2 segments)
2. **The mechanism** — exactly how the survival/danger/capability works at a biological level (2-3 segments)
3. **The science** — specific research, studies, measurements, named researchers where available (1-2 segments)
4. **Comparative context** — how this compares to other animals, to humans, to what science expected (1-2 segments)
5. **Geographic/real-world context** — where this happens, who it affects, scale of the phenomenon (1-2 segments)
6. **The implication** — why this matters, what it means for medicine/conservation/the viewer personally (1-2 segments)

If any of these six layers is missing from an entry, the entry is not finished. This framework is what generates depth without padding.

---

## Research Workflow

1. Web-search real stats before writing every script. Look for convergence across WHO, peer-reviewed studies, government agencies, major science journalism.
2. Where a popular "viral" stat is suspected exaggerated, find the real figure and correct it on-camera — this mythbusting beat is a strong retention device.
3. Get mechanism-level detail from real sources: bite force in PSI, venom type, specific protein names, named studies. This is what separates this channel from clip channels.
4. Flag wide-range estimates explicitly rather than picking the most dramatic number.

---

## Remotion vs Stock Placement Rules

| Content type | Segment type | Layout |
|---|---|---|
| Subscribe CTA (hook, mid-video, outro) | `remotion:FactCard` | **`overlay`** — never stock CTA/subscribe footage |
| Like-and-subscribe popup | `remotion:FactCard` | **`overlay`**, `position: "lower-third"` |
| Entry rank reveal (every numbered entry) | `remotion:TitleCard` | **`full`** — mandatory, huge `factNumber` + animal name |
| Chapter open (methodology, final stretch) | `remotion:TitleCard` | `full` |
| Quick stat while narration continues (bite force, LD50, death toll) | `remotion:FactCard` | **`overlay`** (default) |
| Comparative list / ranked stat breakdown (3+ items) | `remotion:FactCard` | `split-right` |
| Retention tease | `remotion:FactCard` | `overlay` |
| Atmospheric narration, animal footage, habitat, action | `stock` or `commons` b-roll only | — |
| Archival/historical incident with no modern footage | `commons` archival or `stock` reconstruction | — |

### Layout decision tree

1. **Is it a subscribe, like, or channel CTA?** → `overlay` Remotion popup over continuing b-roll.
2. **Is it the start of a numbered entry?** → `full` TitleCard rank reveal. Non-negotiable — every entry gets one.
3. **Is it a short single stat (≤ 3 lines on screen)?** → `overlay` popup while b-roll plays.
4. **Is it a comparative list (4+ items, or ranked breakdown)?** → `split-right` FactCard.
5. **Is it a chapter break with no b-roll (methodology, final countdown stretch)?** → `full` TitleCard.
6. **Everything else** — action, habitat, mechanism footage — → plain `stock` / `commons` segment.

### Overlay popup rules

- Set `remotion.layout` to `"overlay"`.
- Set `remotion.overlay.position` to one of: `"lower-third"` (default, best for CTAs and like/subscribe popups), `"center"` (big single-number revelations, death tolls, kill counts), `"top-banner"` (running stat labels, location tags).
- The `description` field names the **full-frame b-roll** playing underneath.
- Include `remotion.broll` with `search_query` and `category` when the source is explicit — the pipeline uses this for fetch.
- Popup copy must be **short and huge** — viewers should read it in under 2 seconds. Title + 1-2 lines max for CTAs; title + 3 stat lines max for info popups.

### Split-right rules

- FactCard renders on the right half. B-roll plays on the left.
- Use only for genuinely comparative content — ranked stat tables, "compared to X" breakdowns, multi-item danger checklists.

### Full-frame rank reveal rules

- Every entry gets exactly one `full` TitleCard or FactCard at its opening segment.
- `factNumber` must be the countdown number (e.g. `"#7"`) rendered **oversized** — this is the single dominant visual element of the card, larger than the title itself.
- Title is the animal's common name. Optional one-line subtitle can carry a single defining stat (e.g. "Kills more people annually than sharks and lions combined").
- No b-roll underneath — this is a pure Remotion frame, full-bleed.

### Ratio target

**~22-28 Remotion segments per 58-minute video**, mixed across layouts:

- 1 rank-reveal `full` TitleCard per numbered entry (10-14 total) — mandatory
- 2-3 overlay subscribe/like CTAs (hook, mid-video/outro) — mandatory
- 2 overlay retention-tease popups — mandatory
- 4-8 overlay quick-stat popups (bite force, death toll, venom yield, speed)
- 2-4 split-right comparison cards (ranked breakdowns, danger checklists)
- 1-2 full TitleCards for chapter opens (methodology, final stretch)

Do not make every segment Remotion. Atmospheric stock/commons footage of the animals themselves is still the backbone (~75-80% of runtime) — Remotion exists to punctuate, not replace, the documentary footage.

---

## Channel Design System

All Remotion segments default to this design system unless a specific beat demands an override. This channel's visual identity is **apex-predator warning signage** — bold, high-contrast, built to read instantly at a glance, never delicate.

**Color palette:**
- Background: near-black gradient, `#0c0c0c` to `#1a1410` (warm black, not cold/blue-black)
- Title text: hot white `#fefaf3`
- Body/stat text: warm ash grey `#c9c2b6`
- Primary accent: apex amber/warning orange `#ff6a1a` (badges, rank numbers, accent bars, bullet dots)
- Secondary accent (extreme-danger moments only — top 3 entries, death-toll reveals): blood red `#c1121f`
- Badge background: primary or secondary accent at 92% opacity

**Typography (mandatory — fill the frame, bigger than you think):**

Text must be **large, legible at a glance on a phone screen, and dominate the available card area**. Small or dainty type is an error on this channel — the whole visual identity is bold impact type, like warning signage or a boxing weigh-in graphic. When in doubt, go bigger than the floor below.

- **Primary font:** Anton — `"Anton, Impact, sans-serif"` — for titles, rank numbers, and badges
- **Body font:** Barlow Condensed, weight 600 — `"Barlow Condensed, Arial Narrow, sans-serif"` — for stat lines and bullet body copy
- **Title weight:** Anton is a single-weight display face — use as-is, never faux-bold
- **Line height:** 1.35 for body, 1.05 for title (Anton is tall and narrow; tight leading reads as more powerful)
- **Text align:** left for FactCard overlay/split-right, center for TitleCard and rank reveals
- **Letter-spacing:** slight positive tracking on badges/labels (0.04em) for a stamped/stenciled feel

**Size floors (never go below these — bigger is preferred over smaller):**

| Composition | Layout | titleSize | bodySize | factNumber | labelSize | contentMaxWidth | padding |
|---|---|---:|---:|---:|---:|---:|---:|
| FactCard | overlay popup | 96 | 56 | 140 (if used) | 34 | 1700 | 44 |
| FactCard | split-right (960px panel) | 108 | 60 | 160 (if used) | 36 | 950 | 40 |
| FactCard | full frame | 130 | 64 | 220 | 38 | 1800 | 72 |
| TitleCard | full frame (rank reveal / chapter) | 150 | 64 | 240 | — | 1800 | 80 |
| TitleCard | overlay popup | 100 | 56 | — | — | 1700 | 44 |

**Space rules:**
- **Rank reveals dominate the entire frame.** The `factNumber` (e.g. "#7") should be the single largest element on screen — bigger than the animal name beneath it. Nothing else competes with it.
- **Overlay popups** render on a wide lower-third or center panel over full-frame b-roll. Text must fill the popup edge-to-edge, not float small inside a large dark box.
- **Split-right** FactCards render in a **960x1080** panel. Set `contentMaxWidth` to **950** so text spans nearly the full right half.
- **Full-frame** cards are poster-sized. Title at 130-150px and rank numbers at 200-240px are normal on this channel, not excessive — err toward the top of the range.
- Keep `padding` tight relative to frame size. Do not pad so much that the type visually shrinks.
- Limit on-screen copy: rank reveal = number + name (+ optional one stat line); info popups = 1 headline + up to 3 short stat lines. Fewer words on screen -> push sizes toward the top of the range.
- Every Remotion `props`, `design.typography`, and `prompt` must cite **Anton** for titles/numbers and **Barlow Condensed** for body, and meet the size floors above.

**Motion personality:** sharp and confident — a hair more kinetic than a slow documentary channel, but still no cheap bounce. Rank numbers **punch in**: quick scale-up from 92% to 100% with a hard spring (~0.35s), title follows 6 frames later, stat line 14 frames after that. Overlay popups use a fast fade-up (~0.4s, 30px travel). No slow float-ins, no confetti, no glitch effects. Hold through full narration line. Hard cut (not soft fade) back to b-roll after rank reveals; soft fade for overlay popups so the underlying b-roll isn't interrupted.

**TitleCard / rank-reveal specifics:** centered layout, `factNumber` largest, title below it, optional one-line stat subtitle beneath that, thick accent bar (6px, amber or blood-red depending on entry severity) beneath the rank number. No decorative iconography. Background same warm-black gradient, optionally with a subtle radial vignette darkening the edges for focus.

---

## script.json Schema

```json
{
  "title": "string",
  "channel": "Apex Archives",
  "script": [
    {
      "beat": 1,
      "label": "string - beat or entry name",
      "segments": [
        {
          "segment_id": 1,
          "content": "narration - target 100-130 words per segment",
          "description": "plain-language visual for editor / full-frame or left-side b-roll if Remotion",
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
- Every item in `script` must be a beat/entry block:
  - `beat`: integer
  - `label`: short beat/entry name (e.g. `"Entry #7 - Golden Poison Frog"`)
  - `segments`: array of segment objects

### Stock / commons segment rules

- `type` is always a 2-element array: `[search_query, category]`
- `search_query`: plain English, pasteable into Storyblocks or Wikimedia Commons. Specific and visual.
- `category`: `"stock"` for Storyblocks / commercial footage; `"commons"` for Wikimedia Commons / public domain archival
- Do **not** use `"type": "broll"`. That is invalid for this pipeline.
- **Identical strings every recurrence** — character-for-character. `"deer roadside dusk"` must appear as `"deer roadside dusk"` every time it is used. No phrasing drift.
- Reuse connective-tissue queries across entries: `"narrator silhouette nature documentary"`, `"research data charts closeup"`, `"nature documentary title transition"`.

### Remotion segment rules

Supported `remotion.layout` values: `"overlay"`, `"split-right"`, `"full"`.

**Overlay popup (subscribe CTAs, like/subscribe popups, quick stats, retention teases):**

```json
{
  "segment_id": 6,
  "content": "This channel ranks the world's deadliest animals using real data, not clickbait. If that's your thing, subscribe - you'll want to see who's number one.",
  "description": "Slow-motion predator stalking through habitat - full-frame b-roll underneath popup",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "overlay",
    "overlay": {
      "position": "lower-third"
    },
    "broll": {
      "search_query": "predator stalking slow motion habitat",
      "category": "stock"
    },
    "props": {
      "title": "Subscribe For The Full Ranking",
      "body": "Real data. Real danger. No clickbait.",
      "factNumber": null,
      "showFactBadge": false,
      "accentColor": "#ff6a1a",
      "textColor": "#fefaf3",
      "bodyColor": "#c9c2b6",
      "backgroundGradient": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
      "fontFamily": "Anton, Impact, sans-serif",
      "bodyFontFamily": "Barlow Condensed, Arial Narrow, sans-serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 44,
      "contentMaxWidth": 1700,
      "titleSize": 100,
      "bodySize": 56,
      "titleWeight": 400,
      "lineHeight": 1.35
    },
    "design": {
      "intent": "Hook subscribe CTA - bold popup over predator b-roll, not stock CTA footage",
      "layout": {
        "mode": "overlay",
        "position": "lower-third",
        "textAlign": "left",
        "verticalAlign": "center",
        "hierarchy": "title dominant, one-line body secondary",
        "contentMaxWidth": "wide lower-third popup panel over full-frame b-roll"
      },
      "typography": {
        "titleFont": "Anton",
        "bodyFont": "Barlow Condensed",
        "titleSize": "100px",
        "bodySize": "56px",
        "titleWeight": 400,
        "lineHeight": 1.35
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
        "text": "#fefaf3",
        "body": "#c9c2b6",
        "accent": "#ff6a1a",
        "accentUsage": "thin accent bar beneath title"
      },
      "motion": {
        "enter": "fast fade-up 30px, ~0.4s",
        "exit": "popup fades as narration continues over b-roll",
        "stagger": "title +0 frames -> body +14 frames",
        "emphasis": "none",
        "easing": "spring, fast"
      },
      "overlays": {
        "badge": "none for CTA popups",
        "decorations": "subtle vignette on popup panel edges only - b-roll stays visible around it",
        "iconography": "none"
      },
      "transitions": {
        "in": "popup rises fast over continuing b-roll",
        "out": "soft fade, b-roll holds"
      },
      "durationHint": "hold through CTA narration line, ~3-4 seconds"
    },
    "prompt": "Full-frame slow-motion predator b-roll plays underneath. Large lower-third Remotion popup panel (Anton 100px title, Barlow Condensed 56px body) rises fast over the footage - not a stock subscribe graphic. Title 'Subscribe For The Full Ranking' in hot white (#fefaf3), one body line below in warm ash grey (#c9c2b6). Warm near-black popup background (#1a1410 to #0c0c0c). Thin amber accent bar (#ff6a1a) beneath the title. B-roll remains visible above and around the panel. Fast fade-up enter, ~0.4s. No badge. Hold through CTA line then fade popup while b-roll continues."
  }
}
```

**Full-frame rank reveal (mandatory at the start of every numbered entry):**

```json
{
  "segment_id": 34,
  "content": "Number seven.",
  "description": "Full-frame Remotion rank reveal - no b-roll, pure graphic",
  "type": "remotion:TitleCard",
  "remotion": {
    "composition": "TitleCard",
    "layout": "full",
    "props": {
      "title": "Golden Poison Frog",
      "factNumber": "#7",
      "subtitle": "Enough toxin in one frog to kill ten grown men",
      "showAccentBar": true,
      "accentColor": "#ff6a1a",
      "textColor": "#fefaf3",
      "subtitleColor": "#c9c2b6",
      "backgroundGradient": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
      "fontFamily": "Anton, Impact, sans-serif",
      "bodyFontFamily": "Barlow Condensed, Arial Narrow, sans-serif",
      "textAlign": "center",
      "verticalAlign": "center",
      "padding": 80,
      "contentMaxWidth": 1800,
      "factNumberSize": 240,
      "titleSize": 150,
      "subtitleSize": 64,
      "titleWeight": 400,
      "lineHeight": 1.05
    },
    "design": {
      "intent": "Punch-in rank reveal - the number is the dominant visual, the name confirms it, one stat line seals the stakes",
      "layout": {
        "textAlign": "center",
        "verticalAlign": "center",
        "hierarchy": "factNumber most dominant, title second, subtitle stat line tertiary",
        "contentMaxWidth": "1800px centered on full frame"
      },
      "typography": {
        "titleFont": "Anton",
        "bodyFont": "Barlow Condensed",
        "titleSize": "150px",
        "bodySize": "64px",
        "factNumberSize": "240px",
        "titleWeight": 400,
        "lineHeight": 1.05
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
        "text": "#fefaf3",
        "body": "#c9c2b6",
        "accent": "#ff6a1a",
        "accentUsage": "thick accent bar beneath rank number"
      },
      "motion": {
        "enter": "hard spring punch-in on factNumber (92% to 100% scale), ~0.35s",
        "exit": "hard cut to entry b-roll",
        "stagger": "factNumber punches in first -> title +6 frames -> subtitle +14 frames",
        "emphasis": "factNumber scale-punch only",
        "easing": "spring, hard"
      },
      "overlays": {
        "badge": "none",
        "decorations": "subtle radial vignette darkening edges for focus",
        "iconography": "none"
      },
      "transitions": {
        "in": "hard cut from previous b-roll into full-frame graphic",
        "out": "hard cut to entry's opening b-roll"
      },
      "durationHint": "hold 2-3 seconds, enough for the narrator's 'number seven' beat"
    },
    "prompt": "Full-bleed Remotion frame, no b-roll. Warm near-black radial gradient background (#1a1410 to #0c0c0c). Centered layout, content max-width 1800px. Enormous Anton rank number '#7' at 240px in amber (#ff6a1a) dominates the frame - punches in with a hard spring scale from 92% to 100% over 0.35s. Below it, the animal name 'Golden Poison Frog' in Anton, 150px, hot white (#fefaf3), enters 6 frames later. Thick amber accent bar (6px) beneath the rank number. One stat subtitle line 'Enough toxin in one frog to kill ten grown men' in Barlow Condensed, 64px, warm ash grey (#c9c2b6), enters 14 frames after the title. Subtle radial vignette on edges. No badge, no iconography. Hold 2-3 seconds. Hard cut to entry b-roll."
  }
}
```

**Split-right FactCard (comparative lists, ranked stat breakdowns):**

```json
{
  "composition": "FactCard",
  "layout": "split-right",
  "props": {
    "title": "string - card headline",
    "body": "string - bullet list, newline-separated",
    "factNumber": null,
    "showFactBadge": true,
    "accentColor": "#ff6a1a",
    "textColor": "#fefaf3",
    "bodyColor": "#c9c2b6",
    "backgroundGradient": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
    "fontFamily": "Anton, Impact, sans-serif",
    "bodyFontFamily": "Barlow Condensed, Arial Narrow, sans-serif",
    "textAlign": "left",
    "verticalAlign": "center",
    "padding": 40,
    "contentMaxWidth": 950,
    "titleSize": 108,
    "bodySize": 60,
    "labelSize": 36,
    "titleWeight": 400,
    "lineHeight": 1.35
  }
}
```

`props`, `design`, and `prompt` must be **consistent**. If they conflict, fix before delivering.

### Remotion compatibility rules

- Use only supported compositions: `FactCard`, `TitleCard`
- Use only supported layouts: `overlay`, `split-right`, `full`
- Put layout on `remotion.layout`, **not** inside `remotion.props`
- Put popup position on `remotion.overlay.position` (`lower-third`, `center`, `top-banner`)
- **Never use stock footage for subscribe, like, or rank-reveal moments** - always `remotion`
- Use `body`, **not** `bullets`
- Use `bodyColor`, **not** `bulletColor`
- Use `factNumber` (string, e.g. `"#7"`) for every entry rank reveal - never embed the number inside `title`
- Use numeric values for size/layout props (`150`, `64`, `1800`), **not** pixel strings like `"48px"`
- **Typography is non-negotiable:** titles/numbers always use `"Anton, Impact, sans-serif"`; body/stat lines always use `"Barlow Condensed, Arial Narrow, sans-serif"`. Meet the size floors in Channel Design System - when unsure, go bigger, not smaller.
- Overlay FactCard: `titleSize` >= 96, `bodySize` >= 56. Split-right: `titleSize` >= 108, `bodySize` >= 60. Full TitleCard/rank reveal: `titleSize` >= 130, `factNumberSize` >= 200.
- Set `contentMaxWidth` to **950** for split-right, **1700+** for overlay popups, **1800** for full frame.
- Do not invent custom render props unless duplicated safely in `design` / `prompt` only.
- If you want bullet-style text on screen, encode it inside `props.body` as newline-separated bullet text.

---

## Worked Examples

### Example A - Stock segment (entry body)

```json
{
  "segment_id": 37,
  "content": "The golden poison frog produces batrachotoxin, a compound so potent that a single specimen carries enough to kill ten adult humans. Unlike snake venom, which must be injected to work, this toxin can be absorbed straight through skin contact, meaning indigenous Embera hunters in Colombia never touch the frog with bare hands. They roll their blowgun darts across its back instead, transferring a lethal dose without ever making direct contact themselves.",
  "description": "Close-up of golden poison frog on rainforest leaf, vivid yellow skin, then cut to blowgun dart being rolled across amphibian's back",
  "type": ["golden poison frog rainforest closeup", "stock"]
}
```

### Example B - Overlay quick-stat popup

```json
{
  "segment_id": 39,
  "content": "One microgram per kilogram of body weight. That's the lethal dose researchers estimate for this toxin in humans - smaller than a grain of salt.",
  "description": "Macro shot of frog skin texture, glistening, full-frame underneath popup",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "overlay",
    "overlay": { "position": "center" },
    "broll": {
      "search_query": "poison frog skin macro texture",
      "category": "stock"
    },
    "props": {
      "title": "1 MICROGRAM / KG",
      "body": "The estimated lethal dose in humans",
      "factNumber": null,
      "showFactBadge": true,
      "accentColor": "#c1121f",
      "textColor": "#fefaf3",
      "bodyColor": "#c9c2b6",
      "backgroundGradient": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
      "fontFamily": "Anton, Impact, sans-serif",
      "bodyFontFamily": "Barlow Condensed, Arial Narrow, sans-serif",
      "textAlign": "center",
      "verticalAlign": "center",
      "padding": 44,
      "contentMaxWidth": 1700,
      "titleSize": 100,
      "bodySize": 56,
      "labelSize": 34,
      "titleWeight": 400,
      "lineHeight": 1.35
    },
    "design": {
      "intent": "Land the exact lethal-dose figure as a hard stat while macro skin footage continues - blood-red accent signals extreme danger tier",
      "layout": {
        "mode": "overlay",
        "position": "center",
        "hierarchy": "stat title dominant, one-line context secondary"
      },
      "typography": {
        "titleFont": "Anton",
        "bodyFont": "Barlow Condensed",
        "titleSize": "100px",
        "bodySize": "56px",
        "titleWeight": 400,
        "lineHeight": 1.35
      },
      "motion": {
        "enter": "fast fade-up, ~0.4s",
        "exit": "fade while b-roll holds"
      }
    },
    "prompt": "Full-frame macro poison-frog-skin b-roll underneath. Centered overlay popup with huge Anton stat title '1 MICROGRAM / KG' at 100px in blood red (#c1121f), one context line 'The estimated lethal dose in humans' at 56px Barlow Condensed below. Blood-red badge signals top-tier danger. Fast fade-up enter. Hold through narration line then fade, b-roll continues."
  }
}
```

### Example C - Split-right comparative FactCard

```json
{
  "segment_id": 41,
  "content": "Compare that to cyanide, compare it to the venom of a black mamba, compare it even to VX nerve agent - gram for gram, this frog's toxin outranks all three by a significant margin.",
  "description": "Left side b-roll: lab vials and warning symbols, generic toxicology visuals",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "split-right",
    "props": {
      "title": "Toxicity Ranked",
      "body": "- Cyanide - lethal dose ~200-300 mg\n- Black mamba venom - ~100 mg\n- VX nerve agent - ~10 mg\n- Batrachotoxin - ~2 mg",
      "factNumber": null,
      "showFactBadge": true,
      "accentColor": "#ff6a1a",
      "textColor": "#fefaf3",
      "bodyColor": "#c9c2b6",
      "backgroundGradient": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
      "fontFamily": "Anton, Impact, sans-serif",
      "bodyFontFamily": "Barlow Condensed, Arial Narrow, sans-serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 40,
      "contentMaxWidth": 950,
      "titleSize": 108,
      "bodySize": 60,
      "labelSize": 36,
      "titleWeight": 400,
      "lineHeight": 1.35
    },
    "design": {
      "intent": "Anchor how extreme the toxin is with a direct ranked comparison against known lethal substances - calm authority, not hype",
      "layout": {
        "textAlign": "left",
        "verticalAlign": "center",
        "hierarchy": "title dominant, four-line ranked list secondary, badge tertiary",
        "contentMaxWidth": "right half of split-screen frame, 950px"
      },
      "typography": {
        "titleFont": "Anton",
        "bodyFont": "Barlow Condensed",
        "titleSize": "108px",
        "bodySize": "60px",
        "titleWeight": 400,
        "lineHeight": 1.35
      },
      "color": {
        "background": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
        "text": "#fefaf3",
        "body": "#c9c2b6",
        "accent": "#ff6a1a",
        "accentUsage": "badge background, bullet dot markers"
      },
      "motion": {
        "enter": "fast fade-up, ~0.4s, stagger 6 frames per line",
        "exit": "hard cut to b-roll",
        "emphasis": "none",
        "easing": "spring"
      },
      "overlays": {
        "badge": "Toxicity Ranking - amber pill, top-left",
        "decorations": "subtle vignette on card edges only",
        "iconography": "none"
      },
      "transitions": {
        "in": "fade from b-roll, card rises from 30px below",
        "out": "hard cut to next b-roll segment"
      },
      "durationHint": "hold through full narration - approximately 8 seconds"
    },
    "prompt": "Warm near-black radial gradient background (#1a1410 to #0c0c0c). Right-half split-screen layout - lab vial and toxicology b-roll plays on the left; this card occupies the right 960px panel. Left-aligned text, vertically centered, content spanning ~950px. Huge Anton title 'Toxicity Ranked' in hot white (#fefaf3), 108px. Four-line ranked bullet list below in Barlow Condensed (#c9c2b6), 60px, line height 1.35, each line staggering in 6 frames apart. Amber badge pill (#ff6a1a) top-left labelled 'Toxicity Ranking', 36px. Fast fade-up enter. Hold through narration (~8 seconds). Hard cut to next b-roll."
  }
}
```

### Example D - Outro like/subscribe popup

```json
{
  "segment_id": 128,
  "content": "If this ranking surprised you, hit like and subscribe - the next one covers animals hiding in plain sight in your own backyard.",
  "description": "Wide shot of narrator-style nature montage - full-frame b-roll underneath popup",
  "type": "remotion:FactCard",
  "remotion": {
    "composition": "FactCard",
    "layout": "overlay",
    "overlay": { "position": "lower-third" },
    "broll": {
      "search_query": "narrator silhouette nature documentary",
      "category": "stock"
    },
    "props": {
      "title": "Like & Subscribe",
      "body": "Next up: the danger hiding in your own backyard",
      "showFactBadge": false,
      "accentColor": "#ff6a1a",
      "textColor": "#fefaf3",
      "bodyColor": "#c9c2b6",
      "backgroundGradient": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
      "fontFamily": "Anton, Impact, sans-serif",
      "bodyFontFamily": "Barlow Condensed, Arial Narrow, sans-serif",
      "textAlign": "left",
      "verticalAlign": "center",
      "padding": 44,
      "contentMaxWidth": 1700,
      "titleSize": 100,
      "bodySize": 56,
      "titleWeight": 400,
      "lineHeight": 1.35
    },
    "prompt": "Outro like/subscribe moment. Full-frame nature-documentary montage b-roll continues underneath. Large lower-third popup - NOT stock subscribe footage. Anton 100px title 'Like & Subscribe', Barlow Condensed 56px body teasing next video. Popup rises fast over b-roll, holds through CTA, fades while montage continues."
  }
}
```

---

## Validation Checklist (mandatory before delivering)

Run all of these silently before presenting the file:

1. **JSON validity** - parse the file. Fail = fix before delivering. Do not deliver malformed JSON.
2. **Word count** - sum all `content` fields. Must be >= 8,000 words. Divide by 145 and report runtime in minutes. If under 55 minutes, do not deliver - expand entries.
3. **Per-entry word count** - every numbered countdown entry must be >= 700 words. Flag and expand any that fall short.
4. **Segment word count** - average should be 100-130 words. Flag entries where most segments are under 80 words.
5. **Type-field consistency** - group all `type[0]` strings, confirm identical string and identical `type[1]` for every recurrence. Fix any near-duplicates.
6. **Title check** - confirm title follows proven formula: concrete stat/comparison + personal stakes + zero ambiguity.
7. **Rank reveal audit** - every numbered entry has exactly one `full`-layout `remotion:TitleCard` (or FactCard) rank reveal with a populated `factNumber` and the animal's name. None missing.
8. **CTA audit** - hook CTA (~segment 5-6), at least one mid-video retention tease, and outro like/subscribe popup are all `remotion` with `layout: "overlay"`. No stock subscribe/like footage anywhere.
9. **Remotion segment audit** - every Remotion segment has: `composition`, `layout`, complete `props`, complete `design`, non-empty `prompt`. `props`, `design`, and `prompt` must be internally consistent.
10. **Remotion count** - ~22-28 Remotion segments total (rank reveals + CTAs + stat popups + comparisons). Fewer than 15 = under-visualized. More than 35 = error.
11. **Typography check** - every Remotion segment cites `"Anton, Impact, sans-serif"` for titles/numbers and `"Barlow Condensed, Arial Narrow, sans-serif"` for body, and meets the size floors (overlay >=96/56, split-right >=108/60, full >=130 title / >=200 factNumber).
12. **Schema check** - top-level object contains `script`, not `segments`.
13. **Stock type check** - every non-Remotion segment uses `type: [search_query, category]`; no `"broll"` strings.
14. **Copy to `/mnt/user-data/outputs/`** and use `present_files`.
15. **Update Topic Rotation Log** with the new entry.

---

## Efficiency Note

User is token/cost-sensitive. Write complete files in a single `bash_tool` heredoc pass. Do not use incremental `str_replace` for large additions. When the user says "make new video," proceed directly - don't ask clarifying questions when this skill's rules already provide the answer. Apply register rotation and title formula automatically.
