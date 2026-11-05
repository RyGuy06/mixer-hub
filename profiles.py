"""Named mixer setups. Connection and Windows startup preferences stay global."""
import copy

PROFILE_KEYS = ("channels", "brightness", "hotkeys")


def snapshot(config):
    return {key: copy.deepcopy(config[key]) for key in PROFILE_KEYS}


def initialize(config):
    if not config.get("profiles"):
        config["profiles"] = {"Default": snapshot(config)}
        config["active_profile"] = "Default"
    if config.get("active_profile") not in config["profiles"]:
        config["active_profile"] = next(iter(config["profiles"]))


def remember(config):
    initialize(config)
    config["profiles"][config["active_profile"]] = snapshot(config)


def validated_name(config, name, *, replacing=None):
    name = name.strip()
    if not name or len(name) > 32 or any(ord(char) < 32 for char in name):
        raise ValueError("Use a name between 1 and 32 characters.")
    if any(existing.casefold() == name.casefold() and existing != replacing
           for existing in config["profiles"]):
        raise ValueError("A profile with this name already exists.")
    return name


def select(config, name):
    if name not in config["profiles"]:
        raise ValueError("This profile no longer exists.")
    remember(config)
    config.update(snapshot(config["profiles"][name]))
    config["active_profile"] = name


def create(config, name):
    name = validated_name(config, name)
    remember(config)
    config["profiles"][name] = snapshot(config)
    config["active_profile"] = name
    return name


def rename(config, name):
    old = config["active_profile"]
    name = validated_name(config, name, replacing=old)
    remember(config)
    config["profiles"] = {name if key == old else key: value
                          for key, value in config["profiles"].items()}
    config["active_profile"] = name
    return name


def delete(config):
    if len(config["profiles"]) <= 1:
        raise ValueError("Keep at least one profile.")
    old = config["active_profile"]
    fallback = next(name for name in config["profiles"] if name != old)
    select(config, fallback)
    del config["profiles"][old]
