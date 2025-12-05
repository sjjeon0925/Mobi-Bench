import os
import re
from typing import Any

from .data_type import (
    Arg,
    EnumValues,
    PredicateDef,
    PredicateInstance,
    PredicateDefDict,
    PredicateInstanceDict,
    PredicateUpdate,
    PredicateUpdateOp,
    ValueInstance,
    ValueType,
    get_unknown,
)
from .utils import find_first

ANNOTATED_INFO = re.compile(r"^\d+_annotated\.json$")
ACTION_PATTERN = re.compile(r"^\d+_actions\.json$")
INSTRUCTION_PATTERN = re.compile(r"^instruction\.txt$")
ANNOTATED_PATTERN = re.compile(r"^\d+_annotated\.png$")
PREDICATES_PATTERN = re.compile(r"predicates\.json$")


def parse_predicate_definition(
    predicate_name: str, raw_predicate: dict[str, Any]
) -> PredicateDef:
    """
    Parse raw predicate definition from JSON format into PredicateDef.
    """
    def parse_predicate_type(predicate_type: str) -> ValueType:
        if predicate_type == "Boolean":
            return ValueType.Boolean
        elif predicate_type == "Text":
            return ValueType.Text
        elif predicate_type == "Number":
            return ValueType.Number
        elif predicate_type == "Date":
            return ValueType.Date
        elif predicate_type == "Time":
            return ValueType.Time
        elif predicate_type == "Enum":
            return ValueType.Enum
        raise ValueError(f"Invalid predicate type: {predicate_type}")

    arguments: dict[str, Arg] = {}
    arg_keys: list[str] = []
    
    if "key_arg_name" in raw_predicate:
        arg_keys = raw_predicate["key_arg_name"]
        if isinstance(arg_keys, str) and arg_keys:
            arg_keys = [arg_keys]
            
    for v in raw_predicate["arguments"]:
        if v["type"] == "Enum":
            arguments[v["name"]] = Arg(
                v["name"],
                parse_predicate_type(v["type"]),
                EnumValues([value.strip('"').strip() for value in v["enum_values"]]),
            )
        else:
            arguments[v["name"]] = Arg(v["name"], parse_predicate_type(v["type"]))
            
    predicate_description = raw_predicate["description"]
    
    return PredicateDef(
        name=predicate_name,
        arguments=arguments,
        description=predicate_description,
        arg_keys=arg_keys,
    )


def parse_predicate_defs(raw_predicates: dict) -> PredicateDefDict:
    """
    Parse raw predicate definitions from JSON format into PredicateDefDict.
    """
    predicate_defs = PredicateDefDict({})
    for predicate_name in raw_predicates:
        predicate_defs[predicate_name] = parse_predicate_definition(
            predicate_name, raw_predicates[predicate_name]
        )
    return predicate_defs


def parse_predicate_update_op(s: str) -> PredicateUpdateOp:
    match s:
        case "Add":
            return PredicateUpdateOp.Add
        case "Update":
            return PredicateUpdateOp.Update
        case "Delete":
            return PredicateUpdateOp.Delete
        case _:
            return PredicateUpdateOp.Update


def parse_predicate_update_list(
    raw_predicate_update_list: list[dict], pred_defs: PredicateDefDict
) -> list[PredicateUpdate]:
    """
    Parse list of predicate updates from raw format.
    """
    predicate_updates: list[PredicateUpdate] = []
    for raw_predicate_update in raw_predicate_update_list:
        predicate_name = raw_predicate_update["Predicate"]
        
        # Create simplified predicate instance
        pred_def = pred_defs[predicate_name]
        arguments: dict[str, ValueInstance] = {}
        
        for arg_name in pred_def.arguments:
            if arg_name in raw_predicate_update:
                value = raw_predicate_update[arg_name]
                arguments[arg_name] = ValueInstance(
                    arg_ty=pred_def.arguments[arg_name],
                    value=value,
                )
            else:
                arguments[arg_name] = ValueInstance(
                    arg_ty=pred_def.arguments[arg_name],
                    value=get_unknown(),
                )
        
        predicate_instance = PredicateInstance(
            predicate_def=pred_def,
            arguments=arguments,
        )
        
        raw_update_rule = (
            "Update"
            if "Update_Rule" not in raw_predicate_update
            else raw_predicate_update["Update_Rule"]
        )
        
        predicate_update = PredicateUpdate(
            predicate=predicate_instance,
            operation=parse_predicate_update_op(raw_update_rule),
        )
        predicate_updates.append(predicate_update)
        
    return predicate_updates