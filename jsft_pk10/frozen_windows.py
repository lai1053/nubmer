from __future__ import annotations

FROZEN_WINDOWS: dict[str, dict] = {
    "jsft_sum12_cap15__gate_g13_26_pos__daily85": {
        "code": "jsft",
        "play": "sum",
        "play_label": "冠亚和",
        "sum_value": 12,
        "cap": 15,
        "selector": "uniform_slots",
        "settlement": "daily_85",
        "net_odds": 10,
        "gate": "g13_26_pos",
        "deployment_level": "core_shadow",
        "champion_ready": False,
        "base_window_id": "sum12_cap15",
        "notes": "Forward shadow only. Champion requires 13 live complete shadow days with gate active.",
    },
}


def resolve_frozen_window(window_id: str | None) -> dict:
    if not window_id:
        window_id = "jsft_sum12_cap15__gate_g13_26_pos__daily85"
    if window_id not in FROZEN_WINDOWS:
        raise ValueError(
            f"Unknown frozen window id: {window_id}. "
            f"Available: {list(FROZEN_WINDOWS.keys())}"
        )
    frozen = dict(FROZEN_WINDOWS[window_id])
    frozen["frozen_window_id"] = window_id
    return frozen
