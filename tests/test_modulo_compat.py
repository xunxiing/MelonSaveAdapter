import ast
import unittest

from src.utils import normalize


class TestModuloCompat(unittest.TestCase):
    def test_ast_percent_emits_mod_node(self) -> None:
        from src.converter.dedup_converter import DedupConverter

        code = """\
if __name__ == "__main__":
    x = 7 % 3
"""
        tree = ast.parse(code)
        cvt = DedupConverter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()

        types = [str((n.get("type") or "")).lower() for n in (cvt.g.to_dict().get("nodes") or [])]
        self.assertIn("mod", types)
        self.assertNotIn("remainder", types)

    def test_add_module_coerces_remainder_operation_type_to_mod(self) -> None:
        import add_module

        module_info = {
            "id": "2327",
            "source_info": {
                "datatype_map_nodename": "Remainder",
                "chip_names_friendly_name": "Remainder",
            },
            "inputs": [],
            "outputs": [],
            "gate_data_type": 2,
        }
        existing_nodes = [
            {
                "OperationType": "Add",
                "GateDataType": "Number",
                "Inputs": [],
                "Outputs": [],
            }
        ]

        node = add_module.create_new_node("RemainderNumberNodeViewModel", module_info, existing_nodes)
        self.assertIsNotNone(node)
        self.assertEqual(node.get("OperationType"), "Mod")

    def test_pipeline_chip_index_has_mod_alias(self) -> None:
        from src.pipeline import build_chip_index_from_moduledef

        module_defs = {
            "2327": {
                "source_info": {
                    "chip_names_friendly_name": "Remainder",
                    "allmod_viewmodel": "RemainderNumberNodeViewModel",
                },
                "inputs": [{"name": "Dividend"}],
                "outputs": [{"name": "Remainder"}],
                "can_modify_data_type": True,
            }
        }
        chip_index = build_chip_index_from_moduledef(module_defs)
        self.assertIn(normalize("Mod"), chip_index)
        self.assertEqual(chip_index[normalize("Mod")]["friendly_name"], "Remainder")


if __name__ == "__main__":
    unittest.main()
