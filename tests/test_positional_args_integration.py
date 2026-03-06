import ast
import unittest

from src.error_handler import ASTError
from src.pipeline import build_chip_index_from_moduledef, build_connections, parse_graph_v2


class TestPositionalArgsIntegration(unittest.TestCase):
    def _convert(self, code: str) -> dict:
        from src.converter.dedup_converter import DedupConverter

        tree = ast.parse(code)
        cvt = DedupConverter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()
        return cvt.g.to_dict()

    @staticmethod
    def _chip_index_for_add() -> dict:
        module_defs = {
            "900": {
                "source_info": {
                    "chip_names_friendly_name": "Add",
                    "allmod_viewmodel": "AddNumbersNodeViewModel",
                },
                "inputs": [{"name": "A"}, {"name": "B"}],
                "outputs": [{"name": "Output"}],
                "can_modify_data_type": True,
            }
        }
        return build_chip_index_from_moduledef(module_defs)

    def test_positional_args_end_to_end(self) -> None:
        code = '''\
a = INPUT("A", "Number")
b = INPUT("B", "Number")

if __name__ == "__main__":
    total = Add(a, b)
    OUTPUT(total, "Sum")
'''

        graph = self._convert(code)

        add_node = next(n for n in (graph.get("nodes") or []) if str(n.get("type", "")).lower() == "add")
        add_id = add_node["id"]
        add_in_ports = {
            e.get("to_port")
            for e in (graph.get("edges") or [])
            if e.get("to_node") == add_id
        }
        self.assertEqual(add_in_ports, {"0", "1"})

        chip_index = self._chip_index_for_add()
        _, node_map = parse_graph_v2(graph, chip_index)
        for i, nid in enumerate(node_map.keys()):
            node_map[nid]["new_full_id"] = f"new_{i}"

        conns = build_connections(graph, node_map, chip_index)
        add_new_id = node_map[add_id]["new_full_id"]
        add_to_indices = {c["to_port_index"] for c in conns if c["to_node_id"] == add_new_id}
        self.assertEqual(add_to_indices, {0, 1})

    def test_keyword_args_backward_compatible(self) -> None:
        code = '''\
a = INPUT(name="A", data_type="Number")
b = INPUT(name="B", data_type="Number")

if __name__ == "__main__":
    total = Add(A=a, B=b)
    OUTPUT(INPUT=total, name="Sum")
'''

        graph = self._convert(code)

        add_node = next(n for n in (graph.get("nodes") or []) if str(n.get("type", "")).lower() == "add")
        add_id = add_node["id"]

        chip_index = self._chip_index_for_add()
        _, node_map = parse_graph_v2(graph, chip_index)
        for i, nid in enumerate(node_map.keys()):
            node_map[nid]["new_full_id"] = f"new_{i}"

        conns = build_connections(graph, node_map, chip_index)
        add_new_id = node_map[add_id]["new_full_id"]
        add_to_indices = {c["to_port_index"] for c in conns if c["to_node_id"] == add_new_id}
        self.assertEqual(add_to_indices, {0, 1})

    def test_output_positional_and_keyword_input_conflict(self) -> None:
        from src.converter.dedup_converter import DedupConverter

        code = '''\
if __name__ == "__main__":
    OUTPUT(1.0, INPUT=2.0, name="X")
'''

        tree = ast.parse(code)
        cvt = DedupConverter()
        with self.assertRaises(ASTError):
            cvt.visit(tree)


if __name__ == "__main__":
    unittest.main()
