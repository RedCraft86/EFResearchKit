"""Compact Audio-owned media projection for authored record-item events."""
from typing import Any


def build_record_media(events: list[dict[str, Any]]) -> dict[str, Any]:
    records = {}
    for event in events:
        if not any(context.get("kind") == "table"
                   and context.get("table") == "SpaceshipMusicTable"
                   and context.get("evidence") == "exactTableField"
                   for context in event.get("contexts", []) if isinstance(context, dict)):
            continue
        media, seen = [], set()
        for candidate in event.get("media", []):
            src = candidate.get("src", "")
            if not src or src in seen:
                continue
            seen.add(src)
            media.append({key: candidate[key] for key in
                          ("src", "rel", "mediaId", "format", "duration", "wwiseMediaEvidence")
                          if key in candidate})
        records[event["id"]] = {"media": media}
    return {"schema": "endfield.audio-record-media.v1", "events": records,
            "evidenceBoundary": "Exact SpaceshipMusicTable events and Audio's decoded Wwise media candidates; runtime branch selection remains unresolved."}
