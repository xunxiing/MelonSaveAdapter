import ast
import unittest

from src.converter.dedup_converter import DedupConverter
from src.error_handler import ASTError


def convert(code: str) -> dict:
    tree = ast.parse(code)
    cvt = DedupConverter()
    cvt.visit(tree)
    cvt.resolve_unresolved()
    cvt.finalize_outputs()
    return cvt.g.to_dict()


class TestIfElseConverter(unittest.TestCase):
    def test_if_else_assignment_emits_branch(self) -> None:
        graph = convert(
            """\
a = INPUT("A", "Number")
b = INPUT("B", "Number")
cond = INPUT("Cond", "Number")

if __name__ == "__main__":
    if cond:
        x = a
    else:
        x = b
    OUTPUT(x, "X")
"""
        )

        branches = [n for n in graph["nodes"] if n.get("type") == "Branch"]
        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0].get("attrs", {}).get("data_type"), "Number")

    def test_missing_entity_else_uses_typed_empty(self) -> None:
        graph = convert(
            """\
obj = INPUT("Obj", "Entity")
cond = INPUT("Cond", "Number")

if __name__ == "__main__":
    if cond:
        target = obj
    OUTPUT(target, "Target")
"""
        )

        entity_empty = [
            n
            for n in graph["nodes"]
            if n.get("type") == "Constant"
            and n.get("attrs", {}).get("value") is None
            and n.get("attrs", {}).get("data_type") == "Entity"
        ]
        self.assertEqual(len(entity_empty), 1)

    def test_position_outputs_merge_as_vector(self) -> None:
        graph = convert(
            """\
a = INPUT("A", "Entity")
b = INPUT("B", "Entity")
cond = INPUT("Cond", "Number")

if __name__ == "__main__":
    if cond:
        pos = Position(a)
    else:
        pos = Position(b)
    OUTPUT(pos, "Pos")
"""
        )

        branches = [n for n in graph["nodes"] if n.get("type") == "Branch"]
        self.assertEqual(len(branches), 1)
        self.assertEqual(branches[0].get("attrs", {}).get("data_type"), "Vector")

    def test_incompatible_branch_types_raise(self) -> None:
        code = """\
obj = INPUT("Obj", "Entity")
cond = INPUT("Cond", "Number")

if __name__ == "__main__":
    if cond:
        x = Position(obj)
    else:
        x = obj
"""
        with self.assertRaises(ASTError):
            convert(code)

    def test_branch_assignments_use_branch_local_updated_values(self) -> None:
        graph = convert(
            """\
z = INPUT("Z", "Number")
cond = INPUT("Cond", "Number")

if __name__ == "__main__":
    if cond:
        z = z + 3
        label = ToString(z)
    else:
        z = z + 5
        label = ToString(z)
    after = z + 10
    OUTPUT(z, "Z Out")
    OUTPUT(label, "Label Out")
    OUTPUT(after, "After Out")
"""
        )

        branches = [n for n in graph["nodes"] if n.get("type") == "Branch"]
        self.assertEqual(
            [n.get("attrs", {}).get("data_type") for n in branches],
            ["Number", "String"],
        )

        node_types = {n["id"]: n["type"] for n in graph["nodes"]}
        tostring_inputs = [
            e
            for e in graph["edges"]
            if node_types.get(e["to_node"]) == "ToString" and e["to_port"] == "Input"
        ]
        self.assertEqual(len(tostring_inputs), 2)
        self.assertEqual(
            [node_types[e["from_node"]] for e in tostring_inputs],
            ["Add", "Add"],
        )

        add_after = [
            n
            for n in graph["nodes"]
            if n.get("type") == "Add"
            and any(
                e["to_node"] == n["id"]
                and e["to_port"] == "A"
                and node_types.get(e["from_node"]) == "Branch"
                for e in graph["edges"]
            )
        ]
        self.assertEqual(len(add_after), 1)


if __name__ == "__main__":
    unittest.main()
