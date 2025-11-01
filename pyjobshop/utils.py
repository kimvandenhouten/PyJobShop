import copy
import dataclasses
import json
import types
from dataclasses import fields, is_dataclass
from typing import Any, get_args, get_origin

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
        else:
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


# The following is a verbatim copy of dataclasses._ATOMIC_TYPES in the
# Python 3.12 source:
_ATOMIC_TYPES = frozenset(
    {
        # Common JSON Serializable types
        types.NoneType,
        bool,
        int,
        float,
        str,
        # Other common types
        complex,
        bytes,
        # Other types that are also unaffected by deepcopy
        types.EllipsisType,
        types.NotImplementedType,
        types.CodeType,
        types.BuiltinFunctionType,
        types.FunctionType,
        type,
        range,
        property,
    }
)


# The following is heavily based on dataclasses.asdict in the Python 3.12
# source.  Changes:
# - remove parameter dict_factory
# - add parameter field_filter
def dictify(obj, field_filter=lambda cls, field: True):
    if type(obj) in _ATOMIC_TYPES:
        return obj
    if dataclasses.is_dataclass(obj):
        # fast path for the common case
        return {
            f.name: dictify(getattr(obj, f.name))
            for f in dataclasses.fields(obj)
            if field_filter(obj.__class__, f)
        }
    if isinstance(obj, tuple) and hasattr(obj, "_fields"):
        # obj is a namedtuple.  (For more details, consult original Python
        # source.)
        return type(obj)(*[dictify(v) for v in obj])
    if isinstance(obj, (list, tuple)):
        # Assume we can create an object of this type by passing in a
        # generator (which is not true for namedtuples, handled
        # above).
        return type(obj)(dictify(v) for v in obj)
    if isinstance(obj, dict):
        if hasattr(type(obj), "default_factory"):
            # obj is a defaultdict, which has a different constructor from
            # dict as it requires the default_factory as its first arg.
            result = type(obj)(getattr(obj, "default_factory"))
            for k, v in obj.items():
                result[dictify(k)] = dictify(v)
            return result
        return type(obj)((dictify(k), dictify(v)) for k, v in obj.items())
    return copy.deepcopy(obj)


def to_json(obj: Any, field_filter=lambda cls, field: True, indent=2) -> str:
    as_dict = dictify(obj, field_filter)
    return json.dumps(as_dict, indent=indent)
