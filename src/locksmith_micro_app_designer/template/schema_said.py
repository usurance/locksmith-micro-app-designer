"""SAID computation for ACDC schema documents.

ACDC schemas carry their SAID in the `$id` field — at the top level and
in every bundled sub-schema block (e.g. the expanded attribute-block
variant inside `a.oneOf`). Unlike micro-app templates, whose `d` SAID is
computed over the recursively key-sorted canonical form (see saidify.py),
schema `$id` SAIDs are computed over the document's **insertion order**,
matching `kli saidify --label '$id'` (which hashes the mapping exactly as
loaded from disk). Schema files are therefore order-sensitive artifacts:
re-serializing one with sorted keys breaks its SAID.
"""
from __future__ import annotations

from typing import Any, Iterator

from keri.core.coring import Saider

SAID_LABEL = "$id"
"""Label field carrying the SAID in ACDC schema documents."""


def compute_schema_said(block: dict[str, Any]) -> str:
    """Compute the SAID of an ACDC schema block over its insertion order."""
    if SAID_LABEL not in block:
        raise KeyError(f"block missing label field: {SAID_LABEL!r}")
    saider, _ = Saider.saidify(sad=dict(block), label=SAID_LABEL)
    return saider.qb64


def saidify_schema_block(block: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of block with its SAID stamped into `$id`."""
    if SAID_LABEL not in block:
        raise KeyError(f"block missing label field: {SAID_LABEL!r}")
    _, stamped = Saider.saidify(sad=dict(block), label=SAID_LABEL)
    return stamped


def verify_schema_said(block: dict[str, Any]) -> bool:
    """True iff block[$id] is the SAID of the block's stored content."""
    claimed = block.get(SAID_LABEL)
    if not isinstance(claimed, str) or not claimed:
        return False
    return compute_schema_said(block) == claimed


def is_bare_said(value: object) -> bool:
    """True iff value is a bare CESR digest primitive (no URI prefix).

    Bare means no scheme/prefix of any kind (rejects `did:`, `sad:`,
    `https://`, ...); the value must parse as a CESR digest (Saider
    rejects non-digest derivation codes and wrong lengths).
    """
    if not isinstance(value, str) or not value:
        return False
    if ":" in value or "/" in value:
        return False
    try:
        Saider(qb64=value)
    except Exception:
        return False
    return True


def iter_said_blocks(doc: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    """Yield (path, block) for every dict in doc carrying a `$id`.

    Root first (path "<root>"), then depth-first in insertion order with
    dotted/bracketed paths matching the repo's xref path style
    (e.g. "properties.a.oneOf[1]").
    """
    def walk(node: Any, path: str) -> Iterator[tuple[str, dict[str, Any]]]:
        if isinstance(node, dict):
            if SAID_LABEL in node:
                yield (path or "<root>", node)
            for key, value in node.items():
                child = f"{path}.{key}" if path else key
                yield from walk(value, child)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                yield from walk(item, f"{path}[{i}]")

    yield from walk(doc, "")
