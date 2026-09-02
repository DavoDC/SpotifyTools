"""Report generation — human-readable markdown reports of sync results."""

import os
from datetime import datetime

ADDED = "added"
UNMATCHED = "unmatched"


def generate_report(report_dir: str,
                    history: dict,
                    low_confidence: list[dict],
                    recovered: list[dict],
                    removed_uris: list[str],
                    total_tracks: int) -> str:
    """Write a markdown report of sync results.

    Args:
        report_dir: directory to write the report to
        history: full history dict (v2 format)
        low_confidence: list of {"track": ..., "matched": ..., "confidence": "low"}
        recovered: list of {"key": ..., "uri": ..., "display": ...} — tracks re-added
        removed_uris: URIs removed from playlist this run
        total_tracks: total tracks in XML library

    Returns:
        Path to the written report file.
    """
    os.makedirs(report_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(report_dir, f"report_{timestamp}.md")

    tracks = history.get("tracks", {})

    all_unmatched = sorted(
        [v["display"] for v in tracks.values() if v.get("state") == UNMATCHED],
        key=str.lower,
    )
    all_exhausted = sorted(
        [v["display"] for v in tracks.values() if v.get("state") == "exhausted"],
        key=str.lower,
    )
    total_matched = sum(1 for v in tracks.values() if v.get("state") == ADDED)
    total_custom = sum(1 for v in tracks.values() if v.get("state") == "custom")

    lines = [
        f"# SpotifyTools - Match Report",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"| Stat | Count |",
        f"|------|-------|",
        f"| Library total | {total_tracks} |",
        f"| Matched (in playlist) | {total_matched} |",
        f"| Unmatched (will retry) | {len(all_unmatched)} |",
        f"| Exhausted (gave up after 5 attempts) | {len(all_exhausted)} |",
        f"| Low confidence (not added, review below) | {len(low_confidence)} |",
        f"| Custom (skipped by design) | {total_custom} |",
        f"",
    ]

    # Recovered tracks (surprising — flagged per user request)
    if recovered:
        lines += [
            f"## Recovered Tracks ({len(recovered)})",
            f"",
            f"These tracks were in history as 'added' but MISSING from the playlist.",
            f"They were re-added automatically. This is unexpected — investigate if recurring.",
            f"",
        ]
        for r in recovered:
            lines.append(f"- {r['display']}")
        lines.append("")

    # Removed tracks
    if removed_uris:
        lines += [
            f"## Removed from Playlist ({len(removed_uris)})",
            f"",
            f"These tracks were in the playlist but not in the XML library.",
            f"They were removed to keep the playlist in sync.",
            f"",
        ]
        for uri in removed_uris:
            lines.append(f"- `{uri}`")
        lines.append("")

    # Unmatched
    lines += [
        f"## Unmatched Tracks ({len(all_unmatched)})",
        f"",
        f"These could not be found on Spotify. Check manually — ",
        f"they may exist under a different name, or not be on Spotify at all.",
        f"",
    ]
    if all_unmatched:
        lines += [f"- {t}" for t in all_unmatched]
    else:
        lines.append("_None — all tracks matched!_")

    # Exhausted
    if all_exhausted:
        lines += [
            f"",
            f"## Exhausted Tracks ({len(all_exhausted)})",
            f"",
            f"These were searched 5+ times and never found. They won't be retried.",
            f"To retry, edit history.json and reset their `search_attempts` to 0.",
            f"",
        ]
        lines += [f"- {t}" for t in all_exhausted]

    # Low confidence — review list
    lines += [
        f"",
        f"## Low Confidence — Not Added ({len(low_confidence)})",
        f"",
        f"A partial Spotify match was found but confidence was too low to add automatically.",
        f"Check each one manually and add to the playlist if correct.",
        f"These will be retried on the next run.",
        f"",
    ]
    if low_confidence:
        lines.append("| Your Track | Closest Spotify Match |")
        lines.append("|------------|-----------------------|")
        for r in sorted(low_confidence, key=lambda x: x["track"].lower()):
            matched = r.get("matched") or "_(no match found)_"
            lines.append(f"| {r['track']} | {matched} |")
    else:
        lines.append("_None this run._")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return report_path
