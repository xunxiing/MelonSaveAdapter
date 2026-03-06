import unittest

from src.pipeline import build_chip_index_from_moduledef, generate_modify_instructions
from src.type_inference import infer_gate_data_types
from src.utils import normalize


class TestTypeModifiabilityPolicy(unittest.TestCase):
    def test_build_chip_index_parses_string_false_flag(self) -> None:
        module_defs = {
            "1282": {
                "source_info": {
                    "chip_names_friendly_name": "Normalize",
                    "allmod_viewmodel": "NormalizeNodeViewModel",
                },
                "inputs": [{"name": "Input"}],
                "outputs": [{"name": "Result"}],
                "can_modify_data_type": "false",
            }
        }
        chip_index = build_chip_index_from_moduledef(module_defs)
        self.assertIn(normalize("Normalize"), chip_index)
        self.assertFalse(chip_index[normalize("Normalize")]["can_modify_data_type"])

    def test_generate_modify_instructions_respects_moduledef_nonmodifiable_flag(self) -> None:
        graph = {
            "nodes": [
                {"id": "n0", "type": "Normalize", "attrs": {"data_type": 2}},
            ],
            "edges": [],
        }
        node_map = {
            "n0": {
                "friendly_name": "Normalize",
                "new_full_id": "normalize_node_0",
                "op_type": "1282",
                # 模拟旧路径中被错误判定为可修改的情况
                "can_modify_data_type": True,
            }
        }
        module_defs = {
            "1282": {
                "source_info": {
                    "chip_names_friendly_name": "Normalize",
                    "allmod_viewmodel": "NormalizeNodeViewModel",
                },
                "inputs": [{"name": "Input", "type": "Vector"}],
                "outputs": [{"name": "Result", "type": "Vector"}],
                "gate_data_type": 8,
                "can_modify_data_type": "false",
            }
        }

        instructions = generate_modify_instructions(
            graph,
            node_map,
            chip_index={},
            module_definitions=module_defs,
            rules={},
        )
        self.assertEqual(instructions, [])

    def test_type_inference_keeps_nonmodifiable_module_gate_default(self) -> None:
        graph = {
            "nodes": [
                {"id": "in_num", "type": "Input", "attrs": {"data_type": 2}},
                {"id": "norm", "type": "Normalize", "attrs": {}},
            ],
            "edges": [
                {"from_node": "in_num", "from_port": "Input", "to_node": "norm", "to_port": "Input"},
            ],
        }
        node_map = {
            "in_num": {"friendly_name": "Input", "op_type": "256"},
            "norm": {"friendly_name": "Normalize", "op_type": "1282"},
        }
        chip_index = {
            normalize("Input"): {"inputs": [], "outputs": ["Input"], "can_modify_data_type": True},
            normalize("Normalize"): {"inputs": ["Input"], "outputs": ["Result"], "can_modify_data_type": False},
        }
        module_defs = {
            "1282": {
                "inputs": [{"name": "Input", "type": "Vector"}],
                "outputs": [{"name": "Result", "type": "Vector"}],
                "gate_data_type": 8,
                "can_modify_data_type": "false",
            }
        }
        inferred = infer_gate_data_types(
            graph,
            node_map=node_map,
            chip_index=chip_index,
            rules={},
            module_defs=module_defs,
        )
        self.assertEqual(inferred.get("norm"), 8)
        self.assertEqual(inferred.get("in_num"), 2)


if __name__ == "__main__":
    unittest.main()
