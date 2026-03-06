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

    def test_variable_int_gate_type_propagates_to_output(self) -> None:
        """
        回归：parse_graph_v2 会把 variable.gateDataType 规整成 int，
        推断阶段必须能识别这个 int 并传播到 Output。
        """
        graph = {
            "nodes": [
                {"id": "v0", "type": "Variable", "attrs": {}},
                {"id": "o0", "type": "Output", "attrs": {}},
            ],
            "edges": [
                {"from_node": "v0", "from_port": "Value", "to_node": "o0", "to_port": "INPUT"},
            ],
        }

        node_map = {
            "v0": {"friendly_name": "Variable", "op_type": None, "var_gate_type": 4},
            "o0": {"friendly_name": "Output", "op_type": "255"},
        }

        chip_index = {
            normalize("Variable"): {"inputs": ["Value", "Set"], "outputs": ["Value"], "can_modify_data_type": True},
            normalize("Output"): {"inputs": ["INPUT"], "outputs": [], "can_modify_data_type": True},
        }

        inferred = infer_gate_data_types(
            graph,
            node_map=node_map,
            chip_index=chip_index,
            rules={},
            module_defs={},
        )

        self.assertEqual(inferred.get("v0"), 4)
        self.assertEqual(inferred.get("o0"), 4)

    def test_multiply_vector_number_feeding_velocity_keeps_vector(self) -> None:
        """
        回归：Multiply 走 same/same 规则时，若其结果接到 Velocity 的 VECTOR 输入，
        且另一路输入是 Number，不应被 Number“锁死”为 2，结果应推断为 8。
        """
        graph = {
            "nodes": [
                {"id": "vec_in", "type": "Input", "attrs": {"data_type": 8}},
                {"id": "num_in", "type": "Input", "attrs": {"data_type": 2}},
                {"id": "mul0", "type": "Multiply", "attrs": {}},
                {"id": "ent_in", "type": "Input", "attrs": {"data_type": 1}},
                {"id": "vel0", "type": "Velocity", "attrs": {}},
            ],
            "edges": [
                {"from_node": "vec_in", "from_port": "Input", "to_node": "mul0", "to_port": "A"},
                {"from_node": "num_in", "from_port": "Input", "to_node": "mul0", "to_port": "B"},
                {"from_node": "ent_in", "from_port": "Input", "to_node": "vel0", "to_port": "object"},
                {"from_node": "mul0", "from_port": "Output", "to_node": "vel0", "to_port": "Velocity"},
            ],
        }

        node_map = {
            "vec_in": {"friendly_name": "Input", "op_type": "256"},
            "num_in": {"friendly_name": "Input", "op_type": "256"},
            "mul0": {"friendly_name": "Multiply", "op_type": "2306"},
            "ent_in": {"friendly_name": "Input", "op_type": "256"},
            "vel0": {"friendly_name": "Velocity", "op_type": "1538"},
        }

        chip_index = {
            normalize("Input"): {"inputs": [], "outputs": ["Input"], "can_modify_data_type": True},
            normalize("Multiply"): {"inputs": ["A", "B"], "outputs": ["Output"], "can_modify_data_type": True},
            normalize("Velocity"): {
                "inputs": ["object", "Velocity"],
                "outputs": ["Velocity"],
                "can_modify_data_type": False,
            },
        }

        rules = {
            "2306": {"inputs": ["same", "same"], "outputs": ["same"]},
        }

        module_defs = {
            "2306": {
                "inputs": [{"name": "A", "type": "DECIMAL"}, {"name": "B", "type": "DECIMAL"}],
                "outputs": [{"name": "A × B", "type": "DECIMAL"}],
                "gate_data_type": 2,
            },
            "1538": {
                "inputs": [{"name": "object", "type": "ENTITY"}, {"name": "Velocity", "type": "VECTOR"}],
                "outputs": [{"name": "Velocity", "type": "VECTOR"}],
                "gate_data_type": 0,
            },
        }

        inferred = infer_gate_data_types(
            graph,
            node_map=node_map,
            chip_index=chip_index,
            rules=rules,
            module_defs=module_defs,
        )

        self.assertEqual(inferred.get("mul0"), 8)
        self.assertEqual(inferred.get("num_in"), 2)


if __name__ == "__main__":
    unittest.main()
