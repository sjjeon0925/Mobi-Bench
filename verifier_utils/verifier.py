def normalize_predicate_def_json(raw_predicates: dict) -> dict:
    """
    Normalize predicate definition JSON format.
    
    Before:
        {
            "<predicate_name>": {
                "description": <description>,
                "key_arg_name": <key_arg_name>,
                "variables": [
                    {
                        "name": "<variable_name1>",
                        "type": "Text / Number / Boolean / Time / Date",
                    },
                    {
                        "name": "<variable_name2>",
                        "type": "Text / Number / Boolean / Time / Date",
                    },
                ]
            }
        }
    After:
        {
            "<predicate_name>": {
                "key_arg_name": <key_arg_name>,
                "arguments": [
                    {
                        "name": "arg_name1",
                        "type": "arg_type1",
                    },
                    {
                        "name": "arg_name2",
                        "type": "Enum",
                        "enum_values": ["value1", "value2", "value3"],
                    }
                    ...
                ],
                "description": "predicate_description1",
            },
            ...
        }
    """
    normalized_predicates = {}
    for predicate_name in raw_predicates:
        predicate_data = raw_predicates[predicate_name]
        key_arg_name = (
            ""
            if "key_arg_name" not in predicate_data
            else predicate_data["key_arg_name"]
        )
        arguments = predicate_data["variables"]
        normalized_predicates[predicate_name] = {
            "key_arg_name": key_arg_name,
            "arguments": arguments,
            "description": predicate_data["description"],
        }
    return normalized_predicates