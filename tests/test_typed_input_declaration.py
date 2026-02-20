import ast
import unittest


class TestTypedInputDeclaration(unittest.TestCase):
    def test_typed_input_declaration_is_not_registered_as_variable(self) -> None:
        """
        回归：`obj: Entity = INPUT(...)` 应被当作 INPUT 节点别名，
        不能被注册进 variables（否则会被当作 VARIABLE 节点）。
        """
        from src.converter.dedup_converter import DedupConverter

        code = '''\
obj: Entity = INPUT(attrs={"name": "obj", "data_type": 1})

if __name__ == "__main__":
    OUTPUT(INPUT=obj, name="ObjOut")
'''

        tree = ast.parse(code)
        cvt = DedupConverter()
        cvt.visit(tree)
        cvt.resolve_unresolved()
        cvt.finalize_outputs()

        g = cvt.g.to_dict()

        # 1) obj 不应进入 variables（避免被识别成 VARIABLE 声明）
        vars_list = g.get("variables") or []
        self.assertFalse(any(v.get("Key") == "obj" for v in vars_list))

        # 2) 应存在一个 INPUT 与一个 OUTPUT 节点，并且 INPUT 输出连接到 OUTPUT.INPUT
        nodes = g.get("nodes") or []
        edges = g.get("edges") or []

        input_nodes = [n for n in nodes if str(n.get("type", "")).lower() == "input"]
        output_nodes = [n for n in nodes if str(n.get("type", "")).lower() == "output"]

        self.assertEqual(len(input_nodes), 1)
        self.assertEqual(len(output_nodes), 1)

        in_id = input_nodes[0]["id"]
        out_id = output_nodes[0]["id"]

        self.assertTrue(
            any(
                e.get("from_node") == in_id
                and e.get("to_node") == out_id
                and e.get("to_port") == "INPUT"
                for e in edges
            )
        )


if __name__ == "__main__":
    unittest.main()
