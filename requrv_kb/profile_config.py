"""The settings a library bot gets on top of its package: provider, skills folder, this plugin.

* **Provider.** A profile reads only its own ``config.yaml`` and ``.env``, so a bot installed
  from a package would open the "set up a provider" card. It receives the coordinator's (default
  profile's) ``model`` block, the matching ``providers.<name>`` / ``custom_providers`` entry when
  the model uses a named endpoint (how ReQurv Bridge configures Hive), and that provider's own
  key from ``.env``, nothing else. A model or key the bot already has is never replaced.
* **Skills.** ``skills.create_dir`` points at the operator's personal ``skills`` folder, so a skill
  the bot writes is shared through the operator's island.
* **Plugin.** ``requrv-kb`` is enabled in the bot's profile so its library locks apply there.
* **Managed keys.** On update the package's ``config_managed`` keys replace the profile's own.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable

from .paths import PLUGIN_ID, install_root
from .yamlio import load_config, plain, write_config

_MISSING = object()
# Built-in providers whose key the bot needs; any other provider is resolved through Hermes.
_KNOWN_ENV = {
    "requrv-hive": ("REQURV_HIVE_API_KEY", "REQURV_HIVE_BASE_URL"),
    "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL"),
    "custom": ("OPENAI_API_KEY", "OPENAI_BASE_URL"),
    "openrouter": ("OPENROUTER_API_KEY",),
    "anthropic": ("ANTHROPIC_API_KEY",),
}


def lookup(config: Any, parts: list[str]) -> Any:
    node = config
    for part in parts:
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _assign(config: dict, parts: list[str], value: Any) -> None:
    node = config
    for part in parts[:-1]:
        if not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]
    node[parts[-1]] = value


def _discard(config: dict, parts: list[str]) -> None:
    parent = lookup(config, parts[:-1]) if len(parts) > 1 else config
    if isinstance(parent, dict):
        parent.pop(parts[-1], None)


def apply_managed(profile: Path, staged_config: Path | None, keys: Iterable[str]) -> bool:
    """Replace *keys* in the profile's config with the package's values (absent there → removed)."""
    keys = list(keys)
    if not keys:
        return False
    path = Path(profile) / "config.yaml"
    current = load_config(path)
    staged = load_config(staged_config) if staged_config else {}
    before = plain(current)
    for key in keys:
        parts = key.split(".")
        value = lookup(staged, parts)
        if value is _MISSING:
            _discard(current, parts)
        else:
            _assign(current, parts, copy.deepcopy(value))
    if plain(current) == before:
        return False
    write_config(path, current)
    return True


def _named_endpoint(model: Any) -> str:
    provider = str(model.get("provider") or "") if isinstance(model, dict) else ""
    return provider.split(":", 1)[1] if provider.startswith("custom:") else ""


def _provider_env_names(provider: str) -> tuple[str, ...]:
    try:
        from providers import get_provider_profile

        profile = get_provider_profile(provider)
        names = tuple(getattr(profile, "env_vars", ()) or ())
        if names:
            return names
    except Exception:  # an unknown provider id or an older Hermes: fall back to the known table
        pass
    return _KNOWN_ENV.get(provider, ())


def _copy_env(source_env: Path, target_env: Path, names: tuple[str, ...]) -> None:
    if not names or not source_env.is_file():
        return
    from dotenv import dotenv_values

    offered = {k: v for k, v in dotenv_values(source_env).items() if k in names and v}
    present = dotenv_values(target_env) if target_env.is_file() else {}
    missing = [k for k in offered if not present.get(k)]
    if not missing:
        return
    lines = target_env.read_text(encoding="utf-8").splitlines() if target_env.is_file() else []
    lines += [f'{k}="{offered[k]}"' for k in missing]
    target_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        target_env.chmod(0o600)
    except OSError:
        pass


def seed_provider(profile: Path) -> None:
    """Give the bot the coordinator's model, endpoint and provider key when it has none."""
    profile = Path(profile)
    default = install_root()
    source = load_config(default / "config.yaml")
    model = source.get("model")
    if not isinstance(model, dict) or not model:
        return
    path = profile / "config.yaml"
    config = load_config(path)
    changed = False
    if not config.get("model"):
        config["model"] = copy.deepcopy(model)
        changed = True
    target_model = config.get("model") if isinstance(config.get("model"), dict) else {}
    endpoint = _named_endpoint(target_model)
    if endpoint and endpoint == _named_endpoint(model):
        providers = source.get("providers")
        if isinstance(providers, dict) and endpoint in providers:
            mine = config.get("providers") if isinstance(config.get("providers"), dict) else {}
            if endpoint not in mine:
                mine[endpoint] = copy.deepcopy(providers[endpoint])
                config["providers"] = mine
                changed = True
        listed = source.get("custom_providers")
        if isinstance(listed, list):
            matching = [p for p in listed if isinstance(p, dict) and str(p.get("name", "")).lower() == endpoint.lower()]
            mine = config.get("custom_providers") if isinstance(config.get("custom_providers"), list) else []
            names = {str(p.get("name", "")).lower() for p in mine if isinstance(p, dict)}
            added = [copy.deepcopy(p) for p in matching if str(p.get("name", "")).lower() not in names]
            if added:
                config["custom_providers"] = [*mine, *added]
                changed = True
    if changed:
        write_config(path, config)
    provider = str(target_model.get("provider") or "")
    if provider and not provider.startswith("custom:"):
        _copy_env(default / ".env", profile / ".env", _provider_env_names(provider))


def seed_skills_dir(profile: Path, skills_dir: Path) -> None:
    path = Path(profile) / "config.yaml"
    config = load_config(path)
    skills = config.get("skills") if isinstance(config.get("skills"), dict) else {}
    if skills.get("create_dir") == str(skills_dir):
        return
    skills["create_dir"] = str(skills_dir)
    config["skills"] = skills
    write_config(path, config)


def enable_plugin(profile: Path) -> None:
    path = Path(profile) / "config.yaml"
    config = load_config(path)
    plugins = config.get("plugins") if isinstance(config.get("plugins"), dict) else {}
    enabled = plugins.get("enabled") if isinstance(plugins.get("enabled"), list) else []
    disabled = plugins.get("disabled") if isinstance(plugins.get("disabled"), list) else []
    if PLUGIN_ID in enabled and PLUGIN_ID not in disabled:
        return
    if PLUGIN_ID not in enabled:
        enabled.append(PLUGIN_ID)
    plugins["enabled"] = enabled
    if PLUGIN_ID in disabled:
        plugins["disabled"] = [p for p in disabled if p != PLUGIN_ID]
    config["plugins"] = plugins
    write_config(path, config)
