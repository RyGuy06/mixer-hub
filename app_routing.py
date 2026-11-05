"""Priority routing and the remembered audio application library."""


def normalize_apps(names):
    if not isinstance(names, (list, tuple, set)):
        return ()
    return tuple(dict.fromkeys(name.strip().lower() for name in names
                               if isinstance(name, str) and name.strip()))


def priority_for(channel):
    return normalize_apps(channel.get("priority", ()))


def resolve_routes(apps, priorities, available):
    available = set(available)
    return tuple(next((name for name in priority if name in available), "") if priority else app
                 for app, priority in zip(apps, priorities))


def initialize_library(config):
    names = set(normalize_apps(config.get("known_apps", ())))
    setups = [config, *config.get("profiles", {}).values()]
    for setup in setups:
        for channel in setup.get("channels", ()):
            names.add(channel["app"].lower())
            names.update(priority_for(channel))
    config["known_apps"] = sorted(names - {"master", ""})


def validate_app_name(name):
    name = name.strip().lower()
    if name == "master":
        return name
    if (not name.endswith(".exe") or len(name) > 180
            or any(char in name for char in '/\\:*?"<>|')
            or any(ord(char) < 32 for char in name)):
        raise ValueError("Choose a remembered app or enter its executable name, such as game.exe.")
    return name
