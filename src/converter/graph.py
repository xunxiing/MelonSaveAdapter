from __future__ import annotations

from typing import Any, Dict, List, Set

from src.converter.utils import _normalize_id_base


class Graph:
    def __init__(self) -> None:
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        # 额外收集：DSL 中声明的变量定义（用于 chip_variables）
        self.variables: List[Dict[str, Any]] = []
        self._used: Set[str] = set()
        self._ctr: Dict[str, int] = {}

    def next_id(self, type_name: str) -> str:
        base = _normalize_id_base(type_name)
        i = self._ctr.get(base, 0)
        while True:
            nid = f"{base}_{i}"
            i += 1
            if nid not in self._used:
                self._used.add(nid)
                self._ctr[base] = i
                return nid

    def add_node(self, node: Dict[str, Any]) -> None:
        self.nodes.append(node)

    def add_edge(self, from_node: str, from_port: str, to_node: str, to_port: str) -> None:
        self.edges.append(
            {
                "from_node": from_node,
                "from_port": from_port,
                "to_node": to_node,
                "to_port": to_port,
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        # 保持向后兼容：原有字段 nodes / edges 不变，新增加可选字段 variables
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "variables": self.variables,
        }


__all__ = ["Graph"]

