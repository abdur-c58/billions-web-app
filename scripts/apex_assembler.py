"""Assemble Apex Archives script.json from structured topic data."""

from __future__ import annotations

from typing import Any

from apex_helpers import ApexScriptBuilder


def assemble_topic(data: dict[str, Any]) -> dict[str, Any]:
    b = ApexScriptBuilder()
    script: list[dict[str, Any]] = []
    beat = 1

    hook_segs: list[dict[str, Any]] = []
    for item in data["hook"]:
        kind = item["kind"]
        if kind == "stock":
            hook_segs.append(b.stock(item["content"], item["desc"], item["query"], item.get("cat", "stock")))
        elif kind == "overlay_cta":
            hook_segs.append(
                b.overlay_cta(
                    item["content"],
                    item["desc"],
                    item["query"],
                    item["title"],
                    item["body"],
                    item.get("position", "lower-third"),
                )
            )
    script.append({"beat": beat, "label": "Hook", "segments": hook_segs})
    beat += 1

    method_segs: list[dict[str, Any]] = []
    for item in data["methodology"]:
        if item["kind"] == "titlecard":
            method_segs.append(b.titlecard_full(item["content"], item["title"], item["subtitle"]))
        else:
            method_segs.append(b.stock(item["content"], item["desc"], item["query"], item.get("cat", "stock")))
    script.append({"beat": beat, "label": "Methodology", "segments": method_segs})
    beat += 1

    entry_num = 10
    for entry in data["entries"]:
        segs: list[dict[str, Any]] = []
        segs.append(
            b.rank_reveal(
                entry["rank_line"],
                entry["name"],
                entry["num"],
                entry["stat"],
                entry.get("severity", "amber"),
            )
        )
        for item in entry["segments"]:
            kind = item["kind"]
            if kind == "stock":
                segs.append(b.stock(item["content"], item["desc"], item["query"], item.get("cat", "stock")))
            elif kind == "overlay_stat":
                segs.append(
                    b.overlay_stat(
                        item["content"],
                        item["desc"],
                        item["query"],
                        item["title"],
                        item["body"],
                        item.get("position", "center"),
                        item.get("accent"),
                        item.get("badge"),
                    )
                )
            elif kind == "split_card":
                segs.append(
                    b.split_card(
                        item["content"],
                        item["desc"],
                        item["query"],
                        item["title"],
                        item["body"],
                        item.get("badge", "Comparison"),
                    )
                )
        script.append(
            {
                "beat": beat,
                "label": f"Entry #{entry_num} - {entry['name']}",
                "segments": segs,
            }
        )
        beat += 1
        entry_num -= 1

        if entry.get("after_tease"):
            tease = entry["after_tease"]
            script.append(
                {
                    "beat": beat,
                    "label": tease["label"],
                    "segments": [
                        b.overlay_cta(
                            tease["content"],
                            tease["desc"],
                            tease["query"],
                            tease["title"],
                            tease["body"],
                            tease.get("position", "center"),
                        )
                    ],
                }
            )
            beat += 1

    outro_segs: list[dict[str, Any]] = []
    for item in data["outro"]:
        kind = item["kind"]
        if kind == "stock":
            outro_segs.append(b.stock(item["content"], item["desc"], item["query"], item.get("cat", "stock")))
        elif kind == "overlay_cta":
            outro_segs.append(
                b.overlay_cta(
                    item["content"],
                    item["desc"],
                    item["query"],
                    item["title"],
                    item["body"],
                    item.get("position", "lower-third"),
                )
            )
    script.append({"beat": beat, "label": "Outro", "segments": outro_segs})

    return {
        "title": data["title"],
        "channel": "Apex Archives",
        "script": script,
    }
