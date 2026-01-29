import ast
import unittest


class TestSetCreatesSeparateVariableNode(unittest.TestCase):
    def test_set_uses_new_variable_node_instance(self) -> None:
        # Regression: SET(x, x + 1.0) must not wire into the same VARIABLE node that provides x,
        # otherwise the graph becomes a self-loop (VARIABLE -> ... -> VARIABLE) which the editor
        # appears to reject. Instead, SET should create a second VARIABLE node instance for writing.
        from src.converter.dedup_converter import DedupConverter

        code = """\
x: Number = 0.0

if __name__ == "__main__":
    SET(x, x + 1.0)
"""
        tree = ast.parse(code)
        cvt = DedupConverter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()

        g = cvt.g.to_dict()
        edges = g.get("edges") or []

        var_nodes = [
            n
            for n in (g.get("nodes") or [])
            if str(n.get("type", "")).upper() == "VARIABLE"
            and (n.get("attrs") or {}).get("dsl_name") == "x"
        ]
        self.assertEqual(len(var_nodes), 2, "expected two VARIABLE nodes for x (read + write)")

        var_ids = {n["id"] for n in var_nodes}
        write_ids = {
            e["to_node"]
            for e in edges
            if e.get("to_node") in var_ids and e.get("to_port") in ("Value", "Set")
        }
        self.assertEqual(len(write_ids), 1, "expected exactly one write VARIABLE node")
        write_id = next(iter(write_ids))

        read_ids = {e["from_node"] for e in edges if e.get("from_node") in var_ids}
        self.assertTrue(read_ids, "expected x to be read at least once")
        self.assertNotIn(write_id, read_ids, "write VARIABLE node must be different from read node")

        # ensure we never write back into the read node
        for rid in read_ids:
            self.assertFalse(
                any(e.get("to_node") == rid and e.get("to_port") in ("Value", "Set") for e in edges),
                "read VARIABLE node must not receive SET inputs",
            )


if __name__ == "__main__":
    unittest.main()

