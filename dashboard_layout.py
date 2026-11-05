"""Saved dashboard arrangement; independent of mixer profiles and audio routes."""
import copy

DEFAULT_LAYOUT = {"order": ["device", "channels", "activity"], "hidden": [],
                  "view": "top", "guides": True}


def normalize_layout(value):
    value = value if isinstance(value, dict) else {}
    order = value.get("order", [])
    order = order if isinstance(order, list) else []
    order = list(dict.fromkeys(key for key in order if key in DEFAULT_LAYOUT["order"]))
    order.extend(key for key in DEFAULT_LAYOUT["order"] if key not in order)
    hidden = value.get("hidden", [])
    hidden = hidden if isinstance(hidden, list) else []
    return {"order": order, "hidden": [key for key in ("device", "activity") if key in hidden],
            "view": "side" if value.get("view") == "side" else "top",
            "guides": bool(value.get("guides", True))}


def move_widget(layout, source, target):
    result = normalize_layout(layout)
    if source in result["order"] and target in result["order"]:
        target_index = result["order"].index(target)
        result["order"].remove(source)
        result["order"].insert(target_index, source)
    return result


def swap_channels(config, source, target):
    channels = config["channels"]
    if not (0 <= source < len(channels) and 0 <= target < len(channels)):
        raise ValueError("Choose an existing channel.")
    if source == target:
        return False
    # A setup travels as one unit, including any future per-channel settings.
    channels[source], channels[target] = copy.deepcopy(channels[target]), copy.deepcopy(channels[source])
    return True
