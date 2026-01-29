import unittest

from src.type_inference import infer_gate_data_types
from src.utils import normalize


class TestTypeInferencePriority(unittest.TestCase):
    def test_explicit_type_not_lost_on_union_conflict(self) -> None:
        """
        回归：当两个“same/var”节点被 union 在一起且已有不同 fixed 类型时，
        显式 data_type/datatype（更高优先级）不应因为并查集合并顺序而丢失。
        """
        graph = {
            "nodes": [
                {"id": "c0", "type": "Constant", "attrs": {"value": 1}},
                {"id": "d0", "type": "Divide", "attrs": {}},
                {"id": "m0", "type": "Multiply", "attrs": {"datatype": 8}},
                {"id": "o0", "type": "Output", "attrs": {}},
            ],
            "edges": [
                {"from_node": "c0", "from_port": "OUT", "to_node": "d0", "to_port": "A"},
                {"from_node": "c0", "from_port": "OUT", "to_node": "d0", "to_port": "B"},
                # 关键：先让 d0 通过常量固定为 Number(2)，再把 d0 -> m0 做 var-var union
                {"from_node": "d0", "from_port": "Output", "to_node": "m0", "to_port": "B"},
                {"from_node": "m0", "from_port": "Output", "to_node": "o0", "to_port": "INPUT"},
            ],
        }

        node_map = {
            "c0": {"friendly_name": "Constant", "op_type": None},
            "d0": {"friendly_name": "Divide", "op_type": "900"},
            "m0": {"friendly_name": "Multiply", "op_type": "901"},
            "o0": {"friendly_name": "Output", "op_type": "255"},
        }

        chip_index = {
            normalize("Constant"): {"inputs": [], "outputs": ["OUT"], "can_modify_data_type": True},
            normalize("Divide"): {"inputs": ["A", "B"], "outputs": ["Output"], "can_modify_data_type": True},
            normalize("Multiply"): {"inputs": ["A", "B"], "outputs": ["Output"], "can_modify_data_type": True},
            normalize("Output"): {"inputs": ["INPUT"], "outputs": [], "can_modify_data_type": True},
        }

        rules = {
            "900": {"inputs": ["same", "same"], "outputs": ["same"]},
            "901": {"inputs": ["same", "same"], "outputs": ["same"]},
        }

        inferred = infer_gate_data_types(
            graph,
            node_map=node_map,
            chip_index=chip_index,
            rules=rules,
            module_defs={},
        )

        self.assertEqual(inferred.get("m0"), 8)
        self.assertEqual(inferred.get("o0"), 8)


if __name__ == "__main__":
    unittest.main()

