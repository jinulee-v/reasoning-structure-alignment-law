"""Lazily expose shared pipeline utilities."""

from importlib import import_module

_MODULES = ("common", "catala", "workspace_validation", "usage", "run_state")


def __getattr__(name):
    for module_name in _MODULES:
        module = import_module(f"{__name__}.{module_name}")
        if hasattr(module, name):
            value = getattr(module, name)
            globals()[name] = value
            return value
    raise AttributeError(name)
