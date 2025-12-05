from __future__ import annotations
from datetime import datetime
from enum import Enum, auto
from functools import lru_cache
from typing import NewType, Optional
from dataclasses import dataclass, field
from typing import List


@dataclass
class EnumValues:
    values: list[str] = field(default_factory=list)

    def __str__(self):
        return f"[{', '.join(self.values)}]"


class ValueType(Enum):
    Boolean = auto()
    Text = auto()
    Time = auto()
    Date = auto()
    Number = auto()
    Enum = auto()

    def __str__(self):
        match self.name:
            case "Boolean":
                return "Boolean"
            case "Text":
                return "Text" 
            case "Time":
                return "Time"
            case "Date":
                return "Date"
            case "Number":
                return "Number"
            case "Enum":
                return "Enum"

    def __eq__(self, other):
        if type(self).__qualname__ != type(other).__qualname__:
            return NotImplemented
        return self.name == other.name and self.value == other.value


class CmpOp(Enum):
    Equal = auto()  # ==
    NotEqual = auto()  # !=
    GreaterThan = auto()  # >
    GreaterThanOrEqual = auto()  # >=
    LessThan = auto()  # <
    LessThanOrEqual = auto()  # <=

    def __str__(self):
        match self.name:
            case "Equal":
                return "=="
            case "NotEqual":
                return "!="
            case "GreaterThan":
                return ">"
            case "GreaterThanOrEqual":
                return ">="
            case "LessThan":
                return "<"
            case "LessThanOrEqual":
                return "<="

    def __eq__(self, other):
        if type(self).__qualname__ != type(other).__qualname__:
            return NotImplemented
        return self.name == other.name and self.value == other.value


class PredicateUpdateOp(Enum):
    Add = auto()
    Update = auto()
    Delete = auto()

    def __str__(self):
        match self.name:
            case "Add":
                return "Add"
            case "Update":
                return "Update"
            case "Delete":
                return "Delete"
            case _:
                raise ValueError(f"Invalid predicate update operation: {self.name}")

    def __eq__(self, other):
        if type(self).__qualname__ != type(other).__qualname__:
            return NotImplemented
        return self.name == other.name and self.value == other.value


@dataclass
class Arg:
    name: str = ""
    type: ValueType = field(default_factory=lambda: ValueType.Boolean)
    enum_values: EnumValues = field(default_factory=EnumValues)

    def __str__(self):
        if self.type == ValueType.Enum:
            return f"{self.name}: {self.type}{str(self.enum_values)}"
        else:
            return f"{self.name}: {self.type}"


@dataclass
class PredicateDef:
    name: str = ""
    is_action: bool = False
    num_repeat: int = 1
    arguments: dict[str, Arg] = field(default_factory=dict)
    description: str = ""
    arg_keys: list[str] = field(default_factory=list)

    def __str__(self):
        return f"{self.name}({', '.join([str(arg) for arg in self.arguments.values()])}): {self.description}"

    def __eq__(self, other):
        # Don't care about description
        if self.name != other.name:
            return False
        if self.arguments != other.arguments:
            return False
        if self.arg_keys != other.arg_keys:
            return False
        return True


# Simplified singleton classes
class Anything:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __str__(self):
        return "*"

    def __eq__(self, other):
        return str(self) == str(other)


class Unknown:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __str__(self):
        return "?"

    def __eq__(self, other):
        return str(self) == str(other)


class Nothing:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __str__(self):
        return "⊥"

    def __eq__(self, other):
        return str(self) == str(other)


def get_anything():
    return Anything()


def get_nothing():
    return Nothing()


def get_unknown():
    return Unknown()


@dataclass
class ValueInstance:
    arg_ty: Arg
    value: str | int | float | bool | datetime | Anything | Unknown | Nothing = field(
        default_factory=get_anything
    )
    comparison_operator: Optional[CmpOp] = None

    def __str__(self):
        if self.comparison_operator is not None:
            return f"{self.arg_ty.name}=({self.value}, {self.comparison_operator})"
        else:
            return f"{self.arg_ty.name}={self.value}"

    def __hash__(self) -> int:
        return hash(str(self))


@dataclass
class PredicateInstance:
    predicate_def: PredicateDef
    arguments: dict[str, ValueInstance] = field(default_factory=dict)

    def __post_init__(self):
        for arg_name in self.predicate_def.arguments:
            if arg_name not in self.arguments:
                self.arguments[arg_name] = ValueInstance(
                    arg_ty=self.predicate_def.arguments[arg_name],
                    value=get_unknown(),
                )

    def __str__(self):
        specified_args = [
            str(arg) for arg in self.arguments.values() if arg.value != get_anything()
        ]
        return f"{self.predicate_def.name}({', '.join(specified_args)})"

    @property
    def name(self) -> str:
        return self.predicate_def.name


@dataclass
class PredicateUpdate:
    predicate: PredicateInstance
    operation: PredicateUpdateOp = field(default_factory=lambda: PredicateUpdateOp.Add)

    def __str__(self):
        match self.operation:
            case PredicateUpdateOp.Add:
                return f"Add {str(self.predicate)}"
            case PredicateUpdateOp.Update:
                return f"Update to {str(self.predicate)}"
            case PredicateUpdateOp.Delete:
                return f"Delete {str(self.predicate)}"


PredicateDefDict = NewType("PredicateDefDict", dict[str, PredicateDef])
PredicateInstanceDict = NewType("PredicateInstanceDict", dict[str, PredicateInstance])