# Script JSON format

This document explains the `script.json` file you import for each video: the exact shape the app accepts, what every field does, and what happens to the file after you drop it in.

The rules here come straight from the code. Validation runs twice — once in the browser (`lib/script.ts` → `validateScriptPayload`) and again on the server (`viewer/backend/script_format.py` → `validate_script_payload`) — and both enforce the same rules with the same error messages.

---

## 1. The shape at a glance

```json
{
  "title": "What Scientists Keep Finding Beneath Lake Taupō Is Rewriting Everything We Know",
  "channel": "Aotearoa Uncovered",
  "script": [
    {
      "beat": 1,
      "label": "Cold Open Hook",
      "segments": [
        {
          "segment_id": 1,
          "content": "The narration text that gets spoken for this segment.",
          "description": "What the b-roll should show",
          "type": ["search query for stock footage", "stock"]
        }
      ]
    }
  ],
  "thumbnail": {
    "image_prompt": "A paste-ready image prompt for the thumbnail background",
    "overlay_text": {
      "line_1_white": "FIRST LINE",
      "line_2_red": "SECOND LINE"
    }
  }
}
```

There are three levels, plus an optional `thumbnail` brief (section 7b):

| Level | What it is |
|---|---|
| **Root object** | The video: its title, channel, and the list of beats. |
| **Beat** (`script[]`) | A section of the video, like "Cold Open Hook" or "The Real Explanation". Beats become YouTube chapters. |
| **Segment** (`segments[]`) | One chunk of narration plus the visual that plays under it. Each segment becomes one clip in the final video. |

---

## 2. Strict rules (import is rejected if any fail)

These are the only hard requirements. Anything not listed here is optional.

| # | Rule | Error you'll see if broken |
|---|---|---|
| 1 | The file must be valid JSON. | `Invalid JSON: <parser detail>` |
| 2 | The root must be an object `{ ... }`, not an array. | `Script JSON must be an object.` |
| 3 | Beats must live under a top-level key named `script`. Using `segments` at the root is rejected. | `Script must use a top-level "script" array, not "segments".` |
| 4 | `script` must be a non-empty array. | `Script must include a non-empty "script" array.` |
| 5 | Every item in `script` must be an object. | `Beat block N must be an object.` |
| 6 | Every beat must have a non-empty `segments` array. | `Beat block N must include segments.` |
| 7 | Every segment must be an object. | `Each segment must be an object.` |
| 8 | Every segment must have a `segment_id`. | `Each segment needs a segment_id.` |
| 9 | `segment_id` must be unique across the **whole file**, not just within its beat. | `Duplicate segment_id: N` |
| 10 | Every segment must have non-empty `content` (whitespace-only counts as empty). | `Segment N is missing content.` |
| 11 | If present, `thumbnail` must be an object. | `"thumbnail" must be an object.` |
| 12 | If `thumbnail` is present, `thumbnail.image_prompt` must be a non-empty string. | `"thumbnail.image_prompt" must be a non-empty string.` |
| 13 | If present, `thumbnail.overlay_text` must be an object whose values are all strings (write `"1903"`, not `1903`). | `"thumbnail.overlay_text" must be an object.` / `"thumbnail.overlay_text.<key>" must be a string.` |

`segment_id` should be a whole number. The server converts it with `int(...)`, so `3` and `"3"` both work, but something like `"3a"` will crash the import.

Unknown extra keys are ignored, so you can safely add your own notes or metadata to any object.

---

## 3. Root object

| Field | Required | Type | What it does |
|---|---|---|---|
| `script` | **Yes** | array of beats | The video content. See section 4. |
| `title` | Recommended | string | Becomes the project name, the exported MP4 filename, and is used to detect duplicate imports (section 9). Without it the project is called `Project <id>` and exports as `Untitled Video.mp4`. |
| `channel` | Recommended | string | Becomes the export folder: `Documents/ExportedVids/<channel>/exported/<title>.mp4`. Without it the folder is `Unknown Channel`. |
| `thumbnail` | Optional | object | The YouTube thumbnail brief shown by the **Thumbnail** button in the b-roll viewer. See section 7b. |

Characters that Windows forbids in filenames (`< > : " / \ | ? *`) are stripped from `title` and `channel` when building the export path. Accented characters such as `ō` or `ā` are kept and work fine.

---

## 4. Beat object

| Field | Required | Type | What it does |
|---|---|---|---|
| `segments` | **Yes** | non-empty array | The segments in this beat. |
| `beat` | Strongly recommended | integer | The beat number. Chapters are built one per beat, so a beat with no `beat` number is skipped when generating chapters. Keep these unique and increasing (1, 2, 3…). |
| `label` | Strongly recommended | string | The beat's name. This is used **verbatim as the YouTube chapter title**, and as a last-resort b-roll search term. If missing, the chapter is titled `Beat N`. |

### How `label` drives chapters

The **Copy chapters** button turns each beat into a `timestamp title` line, using the start time of that beat's first segment. Beats whose label contains any of these words are treated as non-content and **left out**:

`hook`, `cta`, `call to action`, `subscribe`, `tease`, `teaser`, `retention`, `outro`, `sign off`, `intro`, `cold open`

The match is case-insensitive and on whole words. Because YouTube ignores a chapter list that doesn't start at `0:00`, an `Intro` chapter is always added at `0:00` in place of whatever opened the video.

So for chapters to come out well, name your content beats descriptively ("Colonial-Era Historical Record") and give retention beats an obvious label ("Mid-Video Subscribe CTA"). Avoid the filtered words in content beat names — a beat called "The Hook That Changed History" would be dropped.

---

## 5. Segment object

| Field | Required | Type | What it does |
|---|---|---|---|
| `segment_id` | **Yes** | integer, unique in file | Identifies the segment everywhere. **Also sets narration order** (see below). |
| `content` | **Yes** | non-empty string | The exact words spoken by the voiceover. |
| `description` | Optional | string | A plain-English description of the visual. Used as the b-roll search query when `type` doesn't provide one. |
| `type` | Optional | array, string, or omitted | How the visual is sourced. See section 6. |
| `remotion` | Optional | object | Settings for an animated text card instead of (or on top of) stock footage. See section 7. |
| `delivery` | Optional | string, max 120 chars, no `[ ] . ! ?` | How the voiceover should perform this segment, e.g. `"slower, quiet and somber"`. See below. |

### Voice delivery (`delivery`)

The voiceover uses Fish Audio's `drama-3-preview` model, which reads a direction in square brackets before each sentence and performs it — it is never spoken. The backend adds the default direction `calm, measured storyteller voice, unhurried pace` before **every sentence automatically**; scripts don't need to do anything.

Set `delivery` on a segment only when that segment should sound different. It replaces the default for every sentence in that segment, so write the **whole** direction, not just the change (e.g. `"calm, measured storyteller voice, unhurried pace, quietly somber"`).

- **Never put `[brackets]` or direction words in `content`.** `content` must be exactly the spoken words; Whisper matches the audio back to it for timing.
- Keep it short, plain-language, like briefing a voice actor: emotion, intent, pace.
- Don't use it on most segments — the default is the house style. Typical uses: a tragic moment, a reveal, a tense build-up, the final line.
- The default can be changed with `FISH_TTS_DIRECTION` in `.env.local`.

### Narration order is `segment_id` order, not file order

When generating the voiceover, all `content` strings are collected from every beat, **sorted by `segment_id`**, and joined with spaces. If your IDs are out of order relative to the file, the narration will follow the IDs. The simplest rule: number segments 1, 2, 3… straight through the file, continuing across beats.

---

## 6. The `type` field: where b-roll comes from

There are three regular shapes, plus Remotion (section 7).

### 6a. Array form — `[search_query, category]` (the usual "legacy" format)

```json
"type": ["West Coast New Zealand aerial dense native bush grey rivers", "stock"]
```

- **Item 0** is sent to Pexels/Pixabay as the search query.
- **Item 1** is a category label. `"stock"` is the normal value.
- Missing items are treated as empty strings.

### 6b. String form — a folder name ("folder" format)

```json
"description": "Slow-motion mosquito landing on skin",
"type": "Insects"
```

- The string is a **category / folder name** for your own clip library in storage (`B-Roll/<category>/`), used by **Folder Fetch**.
- The search query becomes `description`, or the category name if there's no description.

### 6c. Omitted

```json
{ "segment_id": 3, "content": "..." }
```

Allowed. With no `type` and no `description`, the b-roll fetcher works out a query on its own (see section 8). You'll get footage, but it will be generic — giving a real query is always better.

### How the whole script's format is detected

The app labels the script **folder** format only if every segment that has a `type` uses the string form *and* there are no Remotion segments. Anything else — any array `type`, any Remotion segment, or a mix — is treated as **legacy**. Segments with no `type` don't affect the decision. Folder Fetch is only available for folder-format scripts.

---

## 7. Remotion segments (animated text cards)

A segment becomes a Remotion card if **any** of these is true:

- `"type": "remotion:FactCard"` or `"type": "remotion:TitleCard"` (also `"remotion:title-card"` style slugs, or just `"remotion"`)
- `"type": ["remotion", "FactCard"]`
- It has a `remotion` object with a `composition`

### Compositions

Only two exist: **`FactCard`** and **`TitleCard`**. An unrecognised name does not cause an error — it **silently falls back to `FactCard`**, so double-check spelling.

### The `remotion` object

```json
"type": "remotion:FactCard",
"remotion": {
  "composition": "FactCard",
  "layout": "overlay",
  "overlay": { "position": "lower-third" },
  "broll": {
    "search_query": "Hokitika coastline aerial",
    "category": "stock"
  },
  "props": {
    "title": "Subscribe for the Real History",
    "body": "Aotearoa's stories hiding in plain sight",
    "accentColor": "#2f6b4f"
  }
}
```

| Field | What it does | Default if omitted |
|---|---|---|
| `composition` | `FactCard` or `TitleCard`. | From `type`, else `FactCard`. |
| `layout` | `split-right` (card on the right, b-roll on the left), `overlay` (card on top of full-frame b-roll), or `full` (card fills the frame, no b-roll). | `FactCard` → `split-right`, `TitleCard` → `full`. Can also be read from `design.layout.mode`. |
| `broll` | Footage for `split-right` and `overlay` layouts. `search_query` (or `query`) is the search; `category` is `stock` or `commons`. Ignored for `full`. | Query falls back to `brollQuery`, then the segment `description`, then `"documentary landscape"`. Category defaults to `stock`. |
| `overlay` | Placement for the `overlay` layout. | `{ "position": "lower-third" }` |
| `props` | Text and styling passed to the card (lists below). | Filled in automatically (below). |
| `design`, `prompt` | Free-form notes carried through with the segment; not required for rendering. | — |

### Props

**FactCard:** `factNumber`, `title`, `body`, `accentColor`, `textColor`, `bodyColor`, `backgroundGradient`, `fontFamily`, `showFactBadge`, `contentMaxWidth`, `titleSize`, `bodySize`, `labelSize`, `titleWeight`, `lineHeight`

**TitleCard:** `title`, `subtitle`, `accentColor`, `textColor`, `subtitleColor`, `backgroundGradient`, `fontFamily`, `showAccentBar`, `contentMaxWidth`, `titleSize`, `subtitleSize`, `titleWeight`, `lineHeight`

**Both:** `textAlign` (`left` / `center` / `right`), `verticalAlign` (`top` / `center` / `bottom`), `padding`

All props are optional. When missing, they're filled in like this:

- **FactCard `factNumber`** is read from text like "Fact 3" or "Fact three" in the content. If none is found, the "FACT N" badge is hidden.
- **FactCard `title`** comes from the segment's `description`, or else the first sentence of `content`.
- **FactCard `body`** is the `content`, with a leading "Fact 3." style prefix removed.
- **TitleCard `title`** is chosen the same way as FactCard's; **`subtitle`** is `description`, or the first 160 characters of `content`.

The `content` is still spoken by the voiceover, exactly like a normal segment.

### Sizes are in 1080p pixels

`titleSize`, `bodySize`, `labelSize`, `subtitleSize`, `padding` and `contentMaxWidth` are written as if the video were 1920×1080. At export they're scaled to the real resolution (×2 for 4K), so the same script looks identical at 1080p and 4K. Leave them out to use the defaults.

When a `split-right` or `overlay` card doesn't set `verticalAlign`, its text is centred vertically. Overlay cards also default to a tighter `padding` of 48 so the text fits the lower-third panel.

---

## 7b. The `thumbnail` brief

An optional top-level object describing the YouTube thumbnail. It isn't rendered into the video; the **Thumbnail** button in the b-roll viewer shows it with copy buttons, so you can paste the prompt into an image generator and add the text yourself.

```json
"thumbnail": {
  "image_prompt": "A cinematic, moody photograph of ... 16:9 aspect ratio, high detail.",
  "overlay_text": {
    "line_1_white": "THE MOUNTAIN",
    "line_2_red": "THAT MOVES",
    "font": "heavy black condensed impact sans-serif, all caps, white fill with black stroke",
    "curiosity_device": "red hand-drawn-style arrow pointing at the crack near the summit",
    "corner_badge": "1903"
  }
}
```

| Field | Required | What it does |
|---|---|---|
| `image_prompt` | **Yes** (if `thumbnail` is present) | The background image prompt. Ask for no text in the image; the text is added on top. |
| `overlay_text` | Optional | Text to place on the thumbnail and how to style it. Every value must be a string. |

Inside `overlay_text`:

- Keys shaped like `line_<number>_<colour>` (e.g. `line_1_white`, `line_2_red`, `line_3_yellow`) are the **text lines**. They're shown in number order, previewed in that colour (any CSS colour name works), and copied together by the overlay **Copy** button.
- Any other key (`font`, `curiosity_device`, `corner_badge`, or your own) is shown as a labelled note, with underscores turned into spaces.

**Copy full brief** copies everything as plain text:

```
IMAGE PROMPT
A cinematic, moody photograph of ...

OVERLAY TEXT
Line 1 (white): THE MOUNTAIN
Line 2 (red): THAT MOVES
Font: heavy black condensed impact sans-serif, ...
Curiosity device: red hand-drawn-style arrow ...
Corner badge: 1903
```

The brief is read from the imported script, so to change it, edit the JSON and re-import.

---

## 8. How the b-roll search query is chosen

For every non-Remotion segment (and the b-roll behind `split-right`/`overlay` cards), the fetcher uses the first non-empty value from this list:

1. The query from `type` (array item 0) or the Remotion `broll.search_query`
2. `description`
3. The beat's `label`
4. The first sentence of `content`
5. `"documentary landscape"`

It never sends an empty query, but steps 3–5 produce vague footage. For good results, give every segment a specific query in `type` or `description`.

---

## 9. What happens when you import

1. **Validated** in the browser, then again on the server, using the rules in section 2.
2. **Duplicate check:** if another project already has the same `title` (case-insensitive, extra spaces ignored), you're asked to confirm an overwrite. Confirming deletes the old project and its exported MP4 from `Documents/ExportedVids`.
3. **Automation choice** from the drop dialog is saved with the project:
   - `none` — import only, you drive every step.
   - `fetch_review` — runs voice, timestamps and b-roll, then waits for you to review.
   - `auto_export` — runs everything through to the final MP4.
4. **Saved** to the project as `script.json`. Re-importing a script into an existing project **deletes its narration audio and timestamps** and resets b-roll progress, because they no longer match the new text.

### The pipeline after import

| Step | Uses from the JSON | Produces |
|---|---|---|
| Voice | Every `content`, in `segment_id` order | `script.mp3` |
| Timestamps (Whisper) | `content` per segment, plus `beat`/`label` | `segment_timestamps.json` |
| B-roll fetch | `type`, `description`, `label`, `remotion.broll` | `broll_selections.json` |
| Export | Everything above | `<title>.mp4` |
| Copy chapters | `beat`, `label`, and segment start times | Clipboard text |

---

## 10. The generated `segment_timestamps.json`

You don't write this file; Whisper creates it by matching the narration audio back to each segment's `content`. It's useful to know its shape when debugging. Each entry carries the segment's beat information forward plus its timing:

```json
{
  "segment_id": 1,
  "beat": 1,
  "label": "Cold Open Hook",
  "content": "Between 1864 and 1867, ...",
  "word_count": 210,
  "description": "Dramatic aerial of West Coast South Island",
  "broll": { "search_query": "West Coast New Zealand aerial ...", "category": "stock" },
  "render_mode": "broll",
  "remotion": null,
  "alignment": { "status": "aligned", "matched_words": 214, "script_words": 214 },
  "timing": {
    "start_seconds": 0.0,
    "end_seconds": 69.3,
    "duration_seconds": 69.3,
    "start_timecode": "00:00:00.000",
    "end_timecode": "00:01:09.300"
  }
}
```

The top of the file also has a `summary` with counts of aligned segments and any `warnings` (for example, "Segment 7: could not align to audio").

---

## 11. A complete example

```json
{
  "title": "The Mysterious Disappearances Haunting New Zealand's West Coast",
  "channel": "Aotearoa Uncovered",
  "script": [
    {
      "beat": 1,
      "label": "Cold Open Hook",
      "segments": [
        {
          "segment_id": 1,
          "content": "Between 1864 and 1867, the West Coast grew from five hundred people to nearly thirty thousand.",
          "description": "Dramatic aerial of the West Coast — native bush, grey rivers, Southern Alps",
          "type": ["West Coast New Zealand aerial native bush Southern Alps", "stock"]
        }
      ]
    },
    {
      "beat": 2,
      "label": "Early Subscribe CTA",
      "segments": [
        {
          "segment_id": 2,
          "content": "This channel covers the history most people were never taught. Subscribe now.",
          "description": "Hokitika coastline aerial under the subscribe card",
          "type": "remotion:FactCard",
          "remotion": {
            "composition": "FactCard",
            "layout": "overlay",
            "overlay": { "position": "lower-third" },
            "broll": { "search_query": "Hokitika coastline aerial", "category": "stock" },
            "props": {
              "title": "Subscribe for the Real History",
              "body": "Aotearoa's stories hiding in plain sight"
            }
          }
        }
      ]
    },
    {
      "beat": 3,
      "label": "Physical and Geological Reality",
      "segments": [
        {
          "segment_id": 3,
          "content": "The terrain itself explains much of what happened.",
          "description": "Fast-flowing braided river through dense rainforest",
          "type": ["braided river dense rainforest New Zealand", "stock"]
        },
        {
          "segment_id": 4,
          "content": "Rivers here can rise several metres in a single afternoon.",
          "type": ["flash flood river rising rapidly", "stock"]
        }
      ]
    }
  ]
}
```

**Copy chapters** on this script gives:

```
0:00 Intro
<start time of segment 3> Physical and Geological Reality
```

Beat 1 is replaced by the `0:00 Intro` marker, and beat 2 is dropped as a subscribe CTA.

---

## 12. Checklist and common mistakes

- [ ] The root key is `script`, not `segments`.
- [ ] Every beat has a non-empty `segments` array.
- [ ] Every segment has a `segment_id` and non-empty `content`.
- [ ] `segment_id`s are whole numbers, unique across the whole file, and run in narration order.
- [ ] Every beat has a unique, increasing `beat` number and a descriptive `label`.
- [ ] Retention beats (hooks, CTAs, outros) have labels containing one of the filtered words; content beats don't.
- [ ] Every b-roll segment has a specific query in `type[0]` or `description`.
- [ ] Remotion compositions are spelled exactly `FactCard` or `TitleCard`.
- [ ] `title` and `channel` are set, so exports are named and filed correctly.
- [ ] If there's a `thumbnail` block, it has an `image_prompt` and every `overlay_text` value is a quoted string.
- [ ] `content` has no `[bracket]` cues; any per-segment voice direction goes in `delivery` (no `[ ] . ! ?`, ≤120 chars).

| Mistake | What happens |
|---|---|
| Root key is `segments` | Import rejected. |
| Same `segment_id` in two different beats | Import rejected (`Duplicate segment_id`). |
| `segment_id`s out of order | Narration is read in ID order, not file order. |
| A beat has no `beat` number | That beat is missing from chapters. |
| A content beat's label includes "hook" or "intro" | That beat is dropped from chapters. |
| No query, no description | Footage is chosen from the beat label or narration — usually generic. |
| Composition misspelled, e.g. `"Factcard"` | Silently rendered as a `FactCard`. |
| Re-importing over a finished project | Its audio and timestamps are deleted and regenerated. |
| `"corner_badge": 1903` (a number) | Import rejected; write `"1903"`. |
