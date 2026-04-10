import json
import unittest

from constantvalue import apply_constant_modifications
from modifier import apply_data_type_modifications
from src.type_inference import infer_gate_data_types
from src.utils import normalize


def _make_game_data_with_chip_graph(nodes):
    return {
        "saveObjectContainers": [
            {
                "saveObjects": {
                    "saveMetaDatas": [
                        {
                            "key": "chip_graph",
                            "stringValue": json.dumps({"Nodes": nodes}, separators=(",", ":")),
                        }
                    ],
                    "mechanicData": [],
                }
            }
        ]
    }


class TestToStringAndLargeArrayRegressions(unittest.TestCase):
    def test_tostring_type_inference_allows_dynamic_input_but_keeps_string_output(self) -> None:
        graph = {
            "nodes": [
                {"id": "in0", "type": "Input", "attrs": {"data_type": 8}},
                {"id": "ts0", "type": "To String", "attrs": {}},
                {"id": "out0", "type": "Output", "attrs": {}},
            ],
            "edges": [
                {"from_node": "in0", "from_port": "Input", "to_node": "ts0", "to_port": "Input"},
                {"from_node": "ts0", "from_port": "String", "to_node": "out0", "to_port": "INPUT"},
            ],
        }
        node_map = {
            "in0": {"friendly_name": "Input", "op_type": "256"},
            "ts0": {"friendly_name": "To String", "op_type": "3595"},
            "out0": {"friendly_name": "Output", "op_type": "255"},
        }
        chip_index = {
            normalize("Input"): {"inputs": [], "outputs": ["Input"], "can_modify_data_type": True},
            normalize("To String"): {
                "inputs": ["Input"],
                "outputs": ["String"],
                "can_modify_data_type": True,
            },
            normalize("Output"): {"inputs": ["INPUT"], "outputs": [], "can_modify_data_type": True},
        }
        rules = {
            "3595": {"inputs": ["same"], "outputs": [4]},
        }
        module_defs = {
            "3595": {
                "gate_data_type": 2,
                "inputs": [{"name": "Input", "type": "Dynamic"}],
                "outputs": [{"name": "String", "type": "STRING"}],
            }
        }

        inferred = infer_gate_data_types(
            graph,
            node_map=node_map,
            chip_index=chip_index,
            rules=rules,
            module_defs=module_defs,
        )

        self.assertEqual(inferred.get("ts0"), 8)
        self.assertEqual(inferred.get("out0"), 4)

    def test_modifier_keeps_tostring_output_as_string(self) -> None:
        node_id = "ToStringNodeViewModel : test-node"
        game_data = _make_game_data_with_chip_graph(
            [
                {
                    "Id": node_id,
                    "OperationType": "ToString",
                    "GateDataType": "Number",
                    "Inputs": [{"DataType": "Number"}],
                    "Outputs": [{"DataType": "String"}],
                    "SaveData": None,
                }
            ]
        )

        updated = apply_data_type_modifications(
            game_data=game_data,
            mod_instructions=[{"node_id": node_id, "new_data_type": 8}],
            rules={"3595": {"inputs": ["same"], "outputs": [4]}},
            module_defs={
                "3595": {
                    "source_info": {"datatype_map_nodename": "ToString"},
                    "inputs": [{"name": "Input", "type": "Dynamic"}],
                    "outputs": [{"name": "String", "type": "STRING"}],
                    "gate_data_type": 2,
                    "can_modify_data_type": True,
                }
            },
        )

        graph_data = json.loads(
            updated["saveObjectContainers"][0]["saveObjects"]["saveMetaDatas"][0]["stringValue"]
        )
        node = graph_data["Nodes"][0]

        self.assertEqual(node["GateDataType"], "Vector")
        self.assertEqual(node["Inputs"][0]["DataType"], "Vector")
        self.assertEqual(node["Outputs"][0]["DataType"], "String")

    def test_large_array_vector_is_serialized_compactly(self) -> None:
        node_id = "ConstantNodeViewModel : big-array"
        game_data = _make_game_data_with_chip_graph(
            [
                {
                    "Id": node_id,
                    "OperationType": "Constant",
                    "GateDataType": "ArrayVector",
                    "Inputs": [],
                    "Outputs": [{"DataType": "ArrayVector"}],
                    "SaveData": json.dumps({"DataValue": "[]"}, separators=(",", ":")),
                }
            ]
        )
        vectors = [[float(i), float(i + 1), float(i + 2)] for i in range(2048)]

        updated = apply_constant_modifications(
            game_data,
            [{"node_id": node_id, "new_value": vectors, "value_type": "array_vector"}],
        )

        chip_graph_string = updated["saveObjectContainers"][0]["saveObjects"]["saveMetaDatas"][0]["stringValue"]
        self.assertNotIn("\n", chip_graph_string)

        graph_data = json.loads(chip_graph_string)
        node = graph_data["Nodes"][0]
        self.assertNotIn("\\n", node["SaveData"])

        save_data = json.loads(node["SaveData"])
        self.assertNotIn("\\n", save_data["DataValue"])

        decoded_vectors = json.loads(save_data["DataValue"])
        self.assertEqual(len(decoded_vectors), len(vectors))
        self.assertEqual(decoded_vectors[0]["x"], 0.0)
        self.assertEqual(decoded_vectors[-1]["z"], 2049.0)


if __name__ == "__main__":
    unittest.main()
