import ast
import unittest


class TestLogicalNoGhostEdges(unittest.TestCase):
    def _convert(self, code: str) -> dict:
        from src.converter.dedup_converter import DedupConverter

        tree = ast.parse(code)
        cvt = DedupConverter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()
        return cvt.g.to_dict()

    @staticmethod
    def _incoming(edges: list[dict], node_id: str, port: str) -> list[dict]:
        return [e for e in edges if e.get("to_node") == node_id and e.get("to_port") == port]

    def test_compare_and_bool_sugar_has_no_placeholder_constant_edges(self) -> None:
        code = """\
a = INPUT("A", 2)
b = INPUT("B", 2)

if __name__ == "__main__":
    ge = a >= b
    gt = a > b
    both = gt and ge
    neg = not both
    OUTPUT(neg, "Neg", 4)
"""
        graph = self._convert(code)
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []

        node_ids_by_type = {}
        for n in nodes:
            t = str(n.get("type") or "").strip().lower()
            node_ids_by_type.setdefault(t, []).append(n["id"])

        ge_id = node_ids_by_type["greater or equal"][0]
        gt_id = node_ids_by_type["greater than"][0]
        and_id = node_ids_by_type["and"][0]
        not_id = node_ids_by_type["not"][0]

        for nid, ports in ((ge_id, ("A", "B")), (gt_id, ("A", "B")), (and_id, ("A", "B")), (not_id, ("A",))):
            for port in ports:
                incoming = self._incoming(edges, nid, port)
                self.assertEqual(
                    len(incoming),
                    1,
                    f"{nid}.{port} expected exactly 1 incoming edge, got {len(incoming)}",
                )
                self.assertIsNotNone(
                    incoming[0].get("line"),
                    f"{nid}.{port} should come from real AST edge with line number",
                )

        constant_ids = {n["id"] for n in nodes if str(n.get("type") or "").strip().lower() == "constant"}
        for nid in (ge_id, gt_id, and_id, not_id):
            for e in edges:
                if e.get("to_node") == nid and e.get("from_node") in constant_ids:
                    self.fail(f"ghost constant edge found: {e}")


if __name__ == "__main__":
    unittest.main()
