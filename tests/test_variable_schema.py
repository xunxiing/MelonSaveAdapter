import json
import unittest


class TestVariableSchema(unittest.TestCase):
    def test_variable_manager_string_schema(self) -> None:
        from src.variable_manager import VariableManager

        definition = VariableManager.create_definition(
            "my_var",
            "String",
            init_value="hello",
            use_string_schema=True,
        )
        self.assertIsInstance(definition.get("GateDataType"), str)
        self.assertEqual(definition.get("GateDataType"), "String")

        node = VariableManager.create_node(
            "my_var",
            "String",
            {"x": 0.0, "y": 0.0},
            use_string_schema=True,
        )
        self.assertIsInstance(node.get("GateDataType"), str)
        self.assertEqual(node.get("GateDataType"), "String")
        self.assertEqual([p.get("DataType") for p in node.get("Inputs")], ["String", "Number"])
        self.assertEqual([p.get("DataType") for p in node.get("Outputs")], ["String"])

    def test_batch_add_modules_schema_detection_ignores_variable_node(self) -> None:
        # Regression: base graph may contain Variable node with OperationType="Variable"(str),
        # but the whole graph can still be int schema. We must not mis-detect and start emitting
        # string-schema nodes (Root/Exit/Constant) into an int graph.
        import batch_add_modules

        existing_nodes = [
            {
                "Id": "VariableNodeViewModel : existing",
                "OperationType": "Variable",
                "Inputs": [],
                "Outputs": [],
            },
            {
                "Id": "AddNumbersNodeViewModel : existing",
                "OperationType": 2304,
                "GateDataType": 2,
                "Inputs": [{"Id": "in", "DataType": 2, "connectedOutputIdModel": None}],
                "Outputs": [{"Id": "out", "DataType": 2, "ConnectedInputsIds": []}],
            },
        ]
        game_data = {
            "saveObjectContainers": [
                {
                    "saveObjects": {
                        "saveMetaDatas": [
                            {
                                "key": "chip_graph",
                                "stringValue": json.dumps(
                                    {"ValidationState": 1, "Nodes": existing_nodes},
                                    ensure_ascii=False,
                                ),
                            },
                            {"key": "chip_inputs", "stringValue": "[]"},
                            {"key": "chip_outputs", "stringValue": "[]"},
                            {"key": "chip_variables", "stringValue": "[]"},
                        ]
                    }
                }
            ]
        }

        updated, created = batch_add_modules.add_modules(
            modules_wanted=[{"type": "input", "name": "Test", "dataType": 2}],
            game_data=game_data,
            module_definitions={},
            cutoff=0.5,
        )
        self.assertEqual(len(created), 1)

        full_id = created[0]["full_id"]
        meta = updated["saveObjectContainers"][0]["saveObjects"]["saveMetaDatas"]
        graph_meta = next(m for m in meta if m.get("key") == "chip_graph")
        graph = json.loads(graph_meta["stringValue"])
        new_node = next(n for n in graph["Nodes"] if n.get("Id") == full_id)

        # int schema input node should keep old numeric OperationType (256)
        self.assertEqual(new_node.get("OperationType"), 256)

    def test_batch_add_modules_variable_respects_string_schema(self) -> None:
        import batch_add_modules

        existing_nodes = [
            {
                "Id": "RootNodeViewModel : existing",
                "OperationType": "Root",
                "GateDataType": "Number",
                "Inputs": [],
                "Outputs": [{"Id": "out", "DataType": "Number", "ConnectedInputsIds": []}],
            }
        ]
        game_data = {
            "saveObjectContainers": [
                {
                    "saveObjects": {
                        "saveMetaDatas": [
                            {
                                "key": "chip_graph",
                                "stringValue": json.dumps(
                                    {"ValidationState": 1, "Nodes": existing_nodes},
                                    ensure_ascii=False,
                                ),
                            },
                            {"key": "chip_inputs", "stringValue": "[]"},
                            {"key": "chip_outputs", "stringValue": "[]"},
                            {"key": "chip_variables", "stringValue": "[]"},
                        ]
                    }
                }
            ]
        }

        updated, created = batch_add_modules.add_modules(
            modules_wanted=[
                {
                    "type": "variable",
                    "key": "my_var",
                    "gateDataType": "String",
                    "value": "hello",
                }
            ],
            game_data=game_data,
            module_definitions={},
            cutoff=0.5,
        )
        self.assertEqual(len(created), 1)

        meta = updated["saveObjectContainers"][0]["saveObjects"]["saveMetaDatas"]

        vars_meta = next(m for m in meta if m.get("key") == "chip_variables")
        vars_list = json.loads(vars_meta.get("stringValue") or "[]")
        var_def = next(v for v in vars_list if v.get("Key") == "my_var")
        self.assertEqual(var_def.get("GateDataType"), "String")

        graph_meta = next(m for m in meta if m.get("key") == "chip_graph")
        graph = json.loads(graph_meta["stringValue"])
        var_node = next(n for n in graph["Nodes"] if n.get("OperationType") == "Variable")
        self.assertEqual(var_node.get("GateDataType"), "String")
        self.assertEqual([p.get("DataType") for p in var_node.get("Inputs")], ["String", "Number"])

    def test_batch_add_modules_variable_is_string_schema_even_in_int_graph(self) -> None:
        import batch_add_modules

        # overall int schema graph (OperationType/DataType are ints)
        existing_nodes = [
            {
                "Id": "AddNumbersNodeViewModel : existing",
                "OperationType": 2304,
                "GateDataType": 2,
                "Inputs": [{"Id": "in", "DataType": 2, "connectedOutputIdModel": None}],
                "Outputs": [{"Id": "out", "DataType": 2, "ConnectedInputsIds": []}],
            }
        ]
        game_data = {
            "saveObjectContainers": [
                {
                    "saveObjects": {
                        "saveMetaDatas": [
                            {
                                "key": "chip_graph",
                                "stringValue": json.dumps(
                                    {"ValidationState": 1, "Nodes": existing_nodes},
                                    ensure_ascii=False,
                                ),
                            },
                            {"key": "chip_inputs", "stringValue": "[]"},
                            {"key": "chip_outputs", "stringValue": "[]"},
                            {"key": "chip_variables", "stringValue": "[]"},
                        ]
                    }
                }
            ]
        }

        updated, created = batch_add_modules.add_modules(
            modules_wanted=[
                {"type": "variable", "key": "my_var", "gateDataType": "Number", "value": 1.0}
            ],
            game_data=game_data,
            module_definitions={},
            cutoff=0.5,
        )
        self.assertEqual(len(created), 1)

        meta = updated["saveObjectContainers"][0]["saveObjects"]["saveMetaDatas"]

        vars_meta = next(m for m in meta if m.get("key") == "chip_variables")
        vars_list = json.loads(vars_meta.get("stringValue") or "[]")
        var_def = next(v for v in vars_list if v.get("Key") == "my_var")
        self.assertEqual(var_def.get("GateDataType"), "Number")

        graph_meta = next(m for m in meta if m.get("key") == "chip_graph")
        graph = json.loads(graph_meta["stringValue"])
        var_node = next(n for n in graph["Nodes"] if n.get("OperationType") == "Variable")
        self.assertEqual(var_node.get("GateDataType"), "Number")
        self.assertEqual([p.get("DataType") for p in var_node.get("Inputs")], ["Number", "Number"])


if __name__ == "__main__":
    unittest.main()
