import copy
import dataclasses
import json
import types
from dataclasses import fields, is_dataclass
from typing import (
    Any,
    Callable,
    ClassVar,
    Protocol,
    Sized,
    get_args,
    get_origin,
    override,
)

_sentinel = object()


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]


class SizedDataclassInstance(DataclassInstance, Sized, Protocol):
    pass


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


class DataclassEncoder(json.JSONEncoder):
    @override
    def default(self, obj):
        if not dataclasses.is_dataclass(obj):
            return super().default(obj)

        cls_flds = (f for f in dataclasses.fields(obj) if f.init)
        result = {"__class__": obj.__class__.__name__}
        result.update((f.name, getattr(obj, f.name)) for f in cls_flds)
        return result


class DataclassDecoder(json.JSONDecoder):
    serializable_classes: dict[str, type[DataclassInstance]]
    delegate_object_hook: Callable[[object], object] | None

    def __init__(self, class_list=(), **kwargs):
        self.delegate_object_hook = kwargs.pop("object_hook", None)
        self.serializable_classes = {}
        for cls in class_list:
            if not dataclasses.is_dataclass(cls):
                raise TypeError(f"{cls.__name__} is not a dataclass")
            if cls.__name__ in self.serializable_classes:
                raise ValueError(
                    f"Duplicate name {cls.__name__} in class_list"
                )
            self.serializable_classes[cls.__name__] = cls
        super().__init__(object_hook=self.object_hook)

    def object_hook(self, obj):
        if self.delegate_object_hook is not None:
            new_obj = self.delegate_object_hook(obj)
            if new_obj is not obj:
                return new_obj
        classname = obj.pop("__class__", _sentinel)
        if classname is _sentinel:
            return obj
        if type(classname) is not str:
            raise ValueError(
                f"Invalid type for class name (__class__): "
                f"expected str, found {type(classname).__name__}"
            )
        cls: type[DataclassInstance] = self.serializable_classes.get(
            classname, None
        )
        if not cls:
            raise TypeError(
                f"Class {classname} not registered for deserialization."
            )
        # noinspection PyDataclass
        cls_flds = [f for f in dataclasses.fields(cls) if f.init]
        kwargs = {}
        for fld in cls_flds:
            val = obj.pop(fld.name, _sentinel)
            if val is _sentinel:
                raise ValueError(
                    f"Field {fld.name} not specified for class {classname}"
                )
            kwargs[fld.name] = val
        if obj:
            keynames = " ".join(str(key) for key in obj)
            raise ValueError(
                f"Extraneous values specified for dataclass {classname}: "
                f"{keynames}"
            )
        # FIXME this is a no-op but deals with a PyCharm squiggle
        cls: type = cls
        try:
            return cls(**kwargs)
        except Exception as e:
            raise ValueError(
                f"Instantiation of dataclass {cls.__name__} "
                "failed. (Does it specify InitVars?)"
            ) from e
