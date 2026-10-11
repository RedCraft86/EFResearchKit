"""Exact authored image tokens and published EnemyTable variant identities."""
from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path

from scripts.webui.assets.table_asset_owners import normalized_asset_stem


def _optional(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else {}


def image_index(assets):
    images = defaultdict(list)
    for row in assets.get("entries", []):
        if row.get("k") == "image":
            images[normalized_asset_stem(row["r"])].append(row)
    return images


def resolve_images(images, token, *, prefer_texture=False):
    matches = images.get(token, [])
    sprites = [r for r in matches if r["r"].startswith("Unity/Sprite/")]
    textures = [r for r in matches if r["r"].startswith("Unity/Texture2D/")]
    preferred = (textures or sprites or matches) if prefer_texture else (sprites or textures or matches)
    return [{"rel": r["r"], "width": r.get("iw"), "height": r.get("ih")}
            for r in sorted(preferred, key=lambda r: r["r"])]


def enrich_presentation(payload, tables, *, data_root: Path, language_root: Path):
    images = image_index(_optional(data_root / "assets" / "index.json"))
    refs = _optional(data_root / "assets" / "gameplay_refs.json").get("entries", {})
    gameplay = _optional(language_root / "gameplay" / "index.json")
    if gameplay and gameplay.get("language") != payload["language"]:
        raise ValueError("Published Gameplay language does not match battle stages")
    variants = {}
    for group in gameplay.get("entries", []):
        if group.get("kind") != "enemy": continue
        for variant in group.get("variants", []):
            variants.setdefault(variant["id"], []).append((group, variant))
    for entry in payload["entries"]:
        entry["art"] = [{**art, **image} for art in entry["artTokens"] for image in resolve_images(images, art["token"], prefer_texture=True)]
        for reward in entry["rewards"]:
            for item in reward["items"]:
                row = tables.get("ItemTable", {}).get(item["id"], {})
                item["art"] = resolve_images(images, row.get("iconId", ""))
        # Include spawn-only enemies below the ordinary catalog later in the UI;
        # this compact exact lookup avoids copying the complete Gameplay index.
    payload["enemyDetails"] = {}
    payload["buffDetails"] = gameplay.get("buffs", {})
    for id, matches in variants.items():
        if len(matches) != 1: continue
        group, variant = matches[0]
        payload["enemyDetails"][id] = {"id": id, "name": variant.get("name") or group.get("title") or id,
            "groupId": group["id"], "templateId": variant.get("templateId"),
            "attrTemplateId": variant.get("attrTemplateId"), "modelId": variant.get("modelId"),
            "aiTemplateId": variant.get("aiTemplateId"), "type": variant.get("displayTypeLabel"),
            "bornBuffs": variant.get("bornBuffs", []), "modifiers": variant.get("attrModifiers", []),
            "art": refs.get(f"enemy:{group['id']}", {}).get("images", [])[:1]}
