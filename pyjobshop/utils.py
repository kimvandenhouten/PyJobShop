import dataclasses
import inspect
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import get_args, get_origin

_sentinel = object()


def from_dict(cls, data: dict):
    """
    Recursively instantiate dataclass `cls` from dict `data`.
    Works for lists of nested dataclasses too.
    """
    kwargs = {}
    for f in fields(cls):
        field_type = f.type
        value = data.get(f.name, None)

        if value is None:
            kwargs[f.name] = (
                f.default_factory()
                if f.default_factory is not dataclasses.MISSING
                else None
            )
            continue

        # Handle lists of dataclasses
        origin = get_origin(field_type)
        args = () if isinstance(field_type, str) else get_args(field_type)
        if origin is list and args and is_dataclass(args[0]):
            inner_type = args[0]
            kwargs[f.name] = [from_dict(inner_type, v) for v in value]
        elif is_dataclass(field_type):
            kwargs[f.name] = from_dict(field_type, value)
        else:
            kwargs[f.name] = value

    return cls(**kwargs)


def _to_jsonable(v):
    """
    Converts a value into a JSON-serializable format.

    Parameters
    ----------
    v : Any
        The value to be converted.

    Returns
    -------
    Any
        A JSON-serializable representation of the input value.
    """
    from pyjobshop.ProblemData import Consumable, Machine, Renewable

    if isinstance(v, (Machine, Renewable, Consumable)):
        as_dict = to_dict(v)
        as_dict["type"] = v.__class__.__name__
        return as_dict
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Enum):
        return v.value  # of v.name
    if isinstance(v, (list, tuple)):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, set):
        return [_to_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _to_jsonable(vv) for k, vv in v.items()}

    # nested object:
    try:
        return to_dict(v)
    except Exception:
        return str(v)


def to_dict(obj, aliases: dict | None = None):
    """
    Converts an object into a dictionary of its initialization arguments.

    This function inspects the `__init__` method of the object's class and
    retrieves the values of the parameters used to initialize the object.
    It supports aliases for parameter names and handles nested objects by
    converting them into JSON-serializable formats.

    Parameters
    ----------
    obj : Any
        The object to be converted.
    aliases : dict | None, optional
        A dictionary mapping parameter names to their aliases, by default None.

    Returns
    -------
    dict
        A dictionary containing the initialization arguments of the object.
    """
    aliases = aliases or {}
    sig = inspect.signature(obj.__class__.__init__)
    out = {}
    for name, param in sig.parameters.items():
        if name == "self" or param.kind in (
            param.VAR_POSITIONAL,
            param.VAR_KEYWORD,
        ):
            continue
        val = getattr(obj, name, _sentinel)
        if val is _sentinel:
            val = getattr(obj, f"_{name}", _sentinel)
        if val is _sentinel and name in aliases:
            alias = aliases[name]
            val = getattr(obj, alias, _sentinel)
            if val is _sentinel and alias.startswith("_"):
                val = getattr(obj, alias.lstrip("_"), _sentinel)
        if val is _sentinel:
            continue  # default
        out[name] = _to_jsonable(val)
    return out
