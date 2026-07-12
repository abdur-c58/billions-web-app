"""Shared Remotion + segment helpers for Apex Archives script builders."""

from __future__ import annotations

CH = {
    "title_font": "Anton, Impact, sans-serif",
    "body_font": "Barlow Condensed, Arial Narrow, sans-serif",
    "bg": "radial-gradient(ellipse at center, #1a1410 0%, #0c0c0c 100%)",
    "text": "#fefaf3",
    "body": "#c9c2b6",
    "amber": "#ff6a1a",
    "red": "#c1121f",
}


class ApexScriptBuilder:
    def __init__(self) -> None:
        self._sid = 0

    def next_id(self) -> int:
        self._sid += 1
        return self._sid

    @property
    def segment_count(self) -> int:
        return self._sid

    def stock(self, content: str, desc: str, query: str, cat: str = "stock") -> dict:
        return {
            "segment_id": self.next_id(),
            "content": content,
            "description": desc,
            "type": [query, cat],
        }

    def overlay_cta(
        self,
        content: str,
        desc: str,
        query: str,
        title: str,
        body: str,
        position: str = "lower-third",
        accent: str | None = None,
    ) -> dict:
        accent = accent or CH["amber"]
        return {
            "segment_id": self.next_id(),
            "content": content,
            "description": desc,
            "type": "remotion:FactCard",
            "remotion": {
                "composition": "FactCard",
                "layout": "overlay",
                "overlay": {"position": position},
                "broll": {"search_query": query, "category": "stock"},
                "props": {
                    "title": title,
                    "body": body,
                    "factNumber": None,
                    "showFactBadge": False,
                    "accentColor": accent,
                    "textColor": CH["text"],
                    "bodyColor": CH["body"],
                    "backgroundGradient": CH["bg"],
                    "fontFamily": CH["title_font"],
                    "bodyFontFamily": CH["body_font"],
                    "textAlign": "left",
                    "verticalAlign": "center",
                    "padding": 44,
                    "contentMaxWidth": 1700,
                    "titleSize": 100,
                    "bodySize": 56,
                    "titleWeight": 400,
                    "lineHeight": 1.35,
                },
                "design": {
                    "intent": "Subscribe/CTA popup over continuing b-roll, never stock CTA footage",
                    "layout": {
                        "mode": "overlay",
                        "position": position,
                        "textAlign": "left",
                        "verticalAlign": "center",
                        "hierarchy": "title dominant, one-line body secondary",
                    },
                    "typography": {
                        "titleFont": "Anton",
                        "bodyFont": "Barlow Condensed",
                        "titleSize": "100px",
                        "bodySize": "56px",
                        "titleWeight": 400,
                        "lineHeight": 1.35,
                    },
                    "color": {
                        "background": CH["bg"],
                        "text": CH["text"],
                        "body": CH["body"],
                        "accent": accent,
                        "accentUsage": "thin accent bar beneath title",
                    },
                    "motion": {
                        "enter": "fast fade-up 30px, ~0.4s",
                        "exit": "popup fades as narration continues",
                        "stagger": "title +0 -> body +14 frames",
                        "emphasis": "none",
                        "easing": "spring, fast",
                    },
                    "overlays": {
                        "badge": "none",
                        "decorations": "subtle vignette on popup edges only",
                        "iconography": "none",
                    },
                    "transitions": {
                        "in": "popup rises fast over continuing b-roll",
                        "out": "soft fade, b-roll holds",
                    },
                    "durationHint": "hold through CTA line, ~3-4 seconds",
                },
                "prompt": (
                    f"Full-frame b-roll ({query}) plays underneath. Large {position} Remotion popup "
                    f"(Anton 100px title, Barlow Condensed 56px body) rises fast — not stock subscribe footage. "
                    f"Title '{title}' in hot white (#fefaf3), body '{body}' in warm ash grey (#c9c2b6). "
                    f"Warm near-black popup background. B-roll visible around panel. Fast fade-up ~0.4s."
                ),
            },
        }

    def overlay_stat(
        self,
        content: str,
        desc: str,
        query: str,
        title: str,
        body: str,
        position: str = "center",
        accent: str | None = None,
        badge: str | None = None,
    ) -> dict:
        accent = accent or CH["amber"]
        return {
            "segment_id": self.next_id(),
            "content": content,
            "description": desc,
            "type": "remotion:FactCard",
            "remotion": {
                "composition": "FactCard",
                "layout": "overlay",
                "overlay": {"position": position},
                "broll": {"search_query": query, "category": "stock"},
                "props": {
                    "title": title,
                    "body": body,
                    "factNumber": None,
                    "showFactBadge": bool(badge),
                    "accentColor": accent,
                    "textColor": CH["text"],
                    "bodyColor": CH["body"],
                    "backgroundGradient": CH["bg"],
                    "fontFamily": CH["title_font"],
                    "bodyFontFamily": CH["body_font"],
                    "textAlign": "center",
                    "verticalAlign": "center",
                    "padding": 44,
                    "contentMaxWidth": 1700,
                    "titleSize": 100,
                    "bodySize": 56,
                    "labelSize": 34,
                    "titleWeight": 400,
                    "lineHeight": 1.35,
                },
                "design": {
                    "intent": "Quick stat popup while b-roll continues",
                    "layout": {"mode": "overlay", "position": position},
                    "typography": {
                        "titleFont": "Anton",
                        "bodyFont": "Barlow Condensed",
                        "titleSize": "100px",
                        "bodySize": "56px",
                    },
                    "motion": {"enter": "fast fade-up ~0.4s", "exit": "fade while b-roll holds"},
                },
                "prompt": (
                    f"Full-frame b-roll underneath. {position} overlay popup. Anton title '{title}' "
                    f"100px, Barlow Condensed body 56px. Fast fade-up. Hold through narration."
                ),
            },
        }

    def rank_reveal(
        self,
        content: str,
        name: str,
        num: str,
        stat: str,
        severity: str = "amber",
    ) -> dict:
        accent = CH["red"] if severity == "red" else CH["amber"]
        return {
            "segment_id": self.next_id(),
            "content": content,
            "description": "Full-frame Remotion rank reveal - no b-roll, pure graphic",
            "type": "remotion:TitleCard",
            "remotion": {
                "composition": "TitleCard",
                "layout": "full",
                "props": {
                    "title": name,
                    "factNumber": num,
                    "subtitle": stat,
                    "showAccentBar": True,
                    "accentColor": accent,
                    "textColor": CH["text"],
                    "subtitleColor": CH["body"],
                    "backgroundGradient": CH["bg"],
                    "fontFamily": CH["title_font"],
                    "bodyFontFamily": CH["body_font"],
                    "textAlign": "center",
                    "verticalAlign": "center",
                    "padding": 80,
                    "contentMaxWidth": 1800,
                    "factNumberSize": 240,
                    "titleSize": 150,
                    "subtitleSize": 64,
                    "titleWeight": 400,
                    "lineHeight": 1.05,
                },
                "design": {
                    "intent": "Punch-in rank reveal — number dominates, name confirms, stat seals stakes",
                    "layout": {
                        "textAlign": "center",
                        "verticalAlign": "center",
                        "hierarchy": "factNumber most dominant, title second, subtitle tertiary",
                        "contentMaxWidth": "1800px centered on full frame",
                    },
                    "typography": {
                        "titleFont": "Anton",
                        "bodyFont": "Barlow Condensed",
                        "titleSize": "150px",
                        "bodySize": "64px",
                        "factNumberSize": "240px",
                        "titleWeight": 400,
                        "lineHeight": 1.05,
                    },
                    "color": {
                        "background": CH["bg"],
                        "text": CH["text"],
                        "body": CH["body"],
                        "accent": accent,
                        "accentUsage": "thick accent bar beneath rank number",
                    },
                    "motion": {
                        "enter": "hard spring punch-in on factNumber (92% to 100%), ~0.35s",
                        "exit": "hard cut to entry b-roll",
                        "stagger": "factNumber first -> title +6 frames -> subtitle +14 frames",
                        "emphasis": "factNumber scale-punch only",
                        "easing": "spring, hard",
                    },
                    "overlays": {
                        "badge": "none",
                        "decorations": "subtle radial vignette darkening edges",
                        "iconography": "none",
                    },
                    "transitions": {
                        "in": "hard cut from previous b-roll into full-frame graphic",
                        "out": "hard cut to entry's opening b-roll",
                    },
                    "durationHint": "hold 2-3 seconds",
                },
                "prompt": (
                    f"Full-bleed Remotion frame. Enormous Anton rank number '{num}' at 240px in {accent}. "
                    f"Title '{name}' 150px hot white. Subtitle '{stat}' 64px Barlow Condensed. "
                    f"Hard spring punch-in. Hold 2-3s. Hard cut to b-roll."
                ),
            },
        }

    def titlecard_full(self, content: str, title: str, subtitle: str) -> dict:
        return {
            "segment_id": self.next_id(),
            "content": content,
            "description": "Full-frame Remotion chapter card, no b-roll",
            "type": "remotion:TitleCard",
            "remotion": {
                "composition": "TitleCard",
                "layout": "full",
                "props": {
                    "title": title,
                    "subtitle": subtitle,
                    "showAccentBar": True,
                    "accentColor": CH["amber"],
                    "textColor": CH["text"],
                    "subtitleColor": CH["body"],
                    "backgroundGradient": CH["bg"],
                    "fontFamily": CH["title_font"],
                    "bodyFontFamily": CH["body_font"],
                    "textAlign": "center",
                    "verticalAlign": "center",
                    "padding": 80,
                    "contentMaxWidth": 1800,
                    "titleSize": 150,
                    "subtitleSize": 64,
                    "titleWeight": 400,
                    "lineHeight": 1.05,
                },
                "design": {
                    "intent": "Chapter-break card signalling shift into methodology/investigation",
                    "layout": {
                        "textAlign": "center",
                        "verticalAlign": "center",
                        "hierarchy": "title dominant, accent bar, subtitle secondary",
                    },
                    "typography": {
                        "titleFont": "Anton",
                        "bodyFont": "Barlow Condensed",
                        "titleSize": "150px",
                        "bodySize": "64px",
                    },
                    "motion": {"enter": "fast fade-up ~0.4s", "exit": "hard cut to b-roll"},
                },
                "prompt": (
                    f"Full-bleed chapter card. Anton title '{title}' 150px, subtitle '{subtitle}' 64px. "
                    f"Thick amber accent bar. Fast fade-up. Hold 3-4s."
                ),
            },
        }

    def split_card(
        self,
        content: str,
        desc: str,
        query: str,
        title: str,
        body: str,
        badge: str = "Comparison",
    ) -> dict:
        return {
            "segment_id": self.next_id(),
            "content": content,
            "description": desc,
            "type": "remotion:FactCard",
            "remotion": {
                "composition": "FactCard",
                "layout": "split-right",
                "broll": {"search_query": query, "category": "stock"},
                "props": {
                    "title": title,
                    "body": body,
                    "factNumber": None,
                    "showFactBadge": True,
                    "accentColor": CH["amber"],
                    "textColor": CH["text"],
                    "bodyColor": CH["body"],
                    "backgroundGradient": CH["bg"],
                    "fontFamily": CH["title_font"],
                    "bodyFontFamily": CH["body_font"],
                    "textAlign": "left",
                    "verticalAlign": "center",
                    "padding": 40,
                    "contentMaxWidth": 950,
                    "titleSize": 108,
                    "bodySize": 60,
                    "labelSize": 36,
                    "titleWeight": 400,
                    "lineHeight": 1.35,
                },
                "design": {
                    "intent": "Comparative ranked list on split-right panel",
                    "layout": {
                        "textAlign": "left",
                        "verticalAlign": "center",
                        "contentMaxWidth": "right half of split-screen frame, 950px",
                    },
                    "typography": {
                        "titleFont": "Anton",
                        "bodyFont": "Barlow Condensed",
                        "titleSize": "108px",
                        "bodySize": "60px",
                    },
                },
                "prompt": (
                    f"Split-right FactCard. Left b-roll: {query}. Right panel Anton title '{title}' 108px, "
                    f"Barlow Condensed body 60px. Badge '{badge}'."
                ),
            },
        }
