#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _find_project_root(start: Path) -> Path:
    cur = start.resolve()
    for p in [cur, *cur.parents]:
        if (p / "moduledef.json").exists() and (p / "芯片教程.txt").exists():
            return p
    raise FileNotFoundError("无法定位项目根目录（缺少 moduledef.json 或 芯片教程.txt）")


PROJECT_ROOT = _find_project_root(Path(__file__).resolve().parent)
MODULEDEF_PATH = PROJECT_ROOT / "moduledef.json"
TUTORIAL_PATH = PROJECT_ROOT / "芯片教程.txt"

# tutorial heading alias -> moduledef friendly-name-like key
ALIASES: dict[str, str] = {
    "touppercase": "uppercase",
    "tolowercase": "stringlowercase",
    "find": "stringfind",
    "prevfrane": "prevframe",  # historical typo in tutorial
    "vectorcrossproduct": "crossproduct",
    "shiftleft": "shiftleftbitop",
    "shiftright": "shiftrightbitop",
    "lookat": "lookatentity",
}

IGNORE_HEADINGS: set[str] = {
    "数学运算，本部分支持python的部分原生语法",
    "ENTITY 类型使用要点",
}

MANUAL_SIGNATURE_LINES: dict[str, str] = {
    "offsetvector": "  位置参数签名: OffsetVector(vector, offset)",
    "fromascii": "  位置参数签名: FromAscii(ascii)",
    "detector": "  位置参数签名: N/A（外部组件，非芯片函数）",
}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _tokens(s: str) -> list[str]:
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    out = [t.lower() for t in re.split(r"[^A-Za-z0-9]+", s2) if t]
    return out


def _tok_key(s: str) -> str:
    ts = _tokens(s)
    ts.sort()
    return "|".join(ts)


def _call_name(raw: str) -> str:
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", raw) if p]
    if not parts:
        return "Module"
    return "".join(p[:1].upper() + p[1:] for p in parts)


def _param_name(raw: str, used: set[str]) -> str:
    p = re.sub(r"[^a-zA-Z0-9]+", "_", raw.strip()).strip("_").lower()
    if not p:
        p = "arg"
    if p[0].isdigit():
        p = f"p_{p}"
    base = p
    i = 2
    while p in used:
        p = f"{base}_{i}"
        i += 1
    used.add(p)
    return p


def _build_module_index(
    module_defs: dict[str, Any],
) -> tuple[dict[str, tuple[str, list[str]]], dict[str, tuple[str, list[str]]]]:
    by_norm: dict[str, tuple[str, list[str]]] = {}
    by_tok: dict[str, tuple[str, list[str]]] = {}
    for _, data in module_defs.items():
        if not isinstance(data, dict):
            continue
        source_info = data.get("source_info") or {}
        if not isinstance(source_info, dict):
            source_info = {}

        friendly = source_info.get("chip_names_friendly_name")
        if not isinstance(friendly, str) or not friendly.strip():
            continue

        inputs = []
        for p in data.get("inputs") or []:
            if isinstance(p, dict):
                name = p.get("name")
                if isinstance(name, str) and name.strip():
                    inputs.append(name.strip())

        candidates = {
            friendly,
            source_info.get("datatype_map_nodename"),
            source_info.get("allmod_viewmodel"),
        }
        for c in candidates:
            if not isinstance(c, str) or not c.strip():
                continue
            rec = (friendly, inputs)
            by_norm.setdefault(_norm(c), rec)
            tk = _tok_key(c)
            if tk:
                by_tok.setdefault(tk, rec)
    return by_norm, by_tok


def _extract_heading_name(tail: str) -> str:
    # strip backticks and split Chinese/English comments in parentheses
    s = tail.strip().lstrip("`").strip()
    s = s.split("(", 1)[0].strip()
    s = s.split("（", 1)[0].strip()
    return s


def main() -> None:
    module_defs = json.loads(MODULEDEF_PATH.read_text(encoding="utf-8"))
    index_norm, index_tok = _build_module_index(module_defs)

    lines = TUTORIAL_PATH.read_text(encoding="utf-8").splitlines()
    new_lines: list[str] = []

    heading_re = re.compile(r"^\s*\d+\.\d+\.\s*(.+?)\s*$")
    inserted = 0
    replaced = 0
    matched = 0
    unmatched: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        m = heading_re.match(line)
        if not m:
            i += 1
            continue

        heading_tail = m.group(1)
        heading_name = _extract_heading_name(heading_tail)
        if heading_name in IGNORE_HEADINGS:
            i += 1
            continue
        heading_norm = _norm(heading_name)
        heading_norm = ALIASES.get(heading_norm, heading_norm)
        rec = index_norm.get(heading_norm)
        if rec is None:
            rec = index_tok.get(_tok_key(heading_name))
        sig = None
        if rec is not None:
            matched += 1
            friendly, inputs = rec
            call = _call_name(friendly)
            used: set[str] = set()
            params = ", ".join(_param_name(p, used) for p in inputs)
            sig = f"  位置参数签名: {call}({params})"
        else:
            sig = MANUAL_SIGNATURE_LINES.get(heading_norm)
            if sig is None:
                unmatched.append(heading_name)
                i += 1
                continue
            matched += 1

        # replace existing signature line if present immediately below
        if i + 1 < len(lines) and "位置参数签名:" in lines[i + 1]:
            # overwrite next line via pointer shift logic
            i += 1
            new_lines.append(sig)
            replaced += 1
        else:
            new_lines.append(sig)
            inserted += 1

        i += 1

    TUTORIAL_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    uniq_unmatched = []
    seen = set()
    for name in unmatched:
        k = _norm(name)
        if not k or k in seen:
            continue
        seen.add(k)
        uniq_unmatched.append(name)
    preview = uniq_unmatched[:12]
    print(
        f"matched={matched} inserted={inserted} replaced={replaced} "
        f"unmatched={len(uniq_unmatched)} file={TUTORIAL_PATH.name}"
    )
    if preview:
        print("unmatched_preview=" + " | ".join(preview))


if __name__ == "__main__":
    main()
