import dataclasses
import json
import types
from typing import (
    Any,
    Callable,
    ClassVar,
    Iterable,
    Protocol,
    Sized,
    override,
)

_sentinel = object()


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]

    def __init__(self, **kwargs) -> None: ...


class SizedDataclassInstance(DataclassInstance, Sized, Protocol):
    pass


class DataclassEncoder(json.JSONEncoder):
    @override
    def default(self, obj):
        if not dataclasses.is_dataclass(obj):
            return super().default(obj)

        cls_flds = (f for f in dataclasses.fields(obj) if f.init)
        result = {"__class__": obj.__class__.__name__}
        result.update((f.name, getattr(obj, f.name)) for f in cls_flds)
        return result


class AbstractDataclassDecoder(json.JSONDecoder):
    serializable_classes: dict[str, type[DataclassInstance]] | None
    delegate_object_hook: Callable[[object], object] | None = None

    def __init__(self, **kwargs):
        self.delegate_object_hook = kwargs.pop("object_hook", None)
        super().__init__(object_hook=self.object_hook, **kwargs)

    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "serializable_classes"):
            raise TypeError(f"{cls.__name__} must define serializable_classes")

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
        try:
            return cls(**kwargs)
        except Exception as e:
            raise ValueError(
                f"Instantiation of dataclass {cls.__name__} "
                "failed. (Does it specify InitVars?)"
            ) from e


def _build_serializable_classes_dict(
    class_list: Iterable[type],
) -> dict[str, type[DataclassInstance]]:
    result: dict[str, type[DataclassInstance]] = {}
    for cls in class_list:
        if cls.__name__ in result:
            raise ValueError(f"Duplicate name {cls.__name__} in class_list")
        if not dataclasses.is_dataclass(cls):
            raise TypeError(f"{cls.__name__} is not a dataclass")
        result[cls.__name__] = cls
    return result


class DataclassDecoder(AbstractDataclassDecoder):
    serializable_classes = None

    def __init__(self, class_list=(), **kwargs):
        self.serializable_classes = _build_serializable_classes_dict(
            class_list
        )
        super().__init__(**kwargs)


def decoder_factory(name: str, class_list: Iterable[type]):
    def class_body(ns):
        ns["serializable_classes"] = _build_serializable_classes_dict(
            class_list
        )

    return types.new_class(
        name, (AbstractDataclassDecoder,), exec_body=class_body
    )
