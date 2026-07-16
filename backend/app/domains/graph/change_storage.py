"""Stable chunk encoding for large, reviewed graph change sets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Iterator

DEFAULT_CHUNK_SIZE = 200
NESTED_GROUPS = {"delete_manifest": "delete", "retained_manifest": "retained"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChangeChunk:
    group_name: str
    chunk_no: int
    items: list[Any]
    payload_json: str
    sha256: str

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class EncodedChangeSet:
    manifest: dict[str, Any]
    chunks: tuple[ChangeChunk, ...]
    sha256: str


def split_groups(change: dict[str, Any]) -> tuple[dict[str, Any], dict[str, list[Any]]]:
    """Separate reviewable arrays while retaining all scalar task metadata."""
    manifest: dict[str, Any] = {}
    groups: dict[str, list[Any]] = {}
    for key, value in change.items():
        if isinstance(value, list):
            groups[key] = value
            continue
        prefix = NESTED_GROUPS.get(key)
        if prefix and isinstance(value, dict):
            nested_meta: dict[str, Any] = {}
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, list):
                    groups[f"{prefix}.{nested_key}"] = nested_value
                else:
                    nested_meta[nested_key] = nested_value
            if nested_meta:
                manifest[key] = nested_meta
            continue
        manifest[key] = value
    return manifest, groups


def _descriptor(chunk: ChangeChunk) -> dict[str, Any]:
    return {
        "group": chunk.group_name,
        "chunk_no": chunk.chunk_no,
        "item_count": chunk.item_count,
        "sha256": chunk.sha256,
    }


def storage_digest(manifest: dict[str, Any], descriptors: Iterable[dict[str, Any]]) -> str:
    ordered = sorted(
        (dict(item) for item in descriptors),
        key=lambda item: (str(item["group"]), int(item["chunk_no"])),
    )
    return sha256_json({"storage_version": 2, "manifest": manifest, "chunks": ordered})


def encode_change_set(change: dict[str, Any], *, chunk_size: int = DEFAULT_CHUNK_SIZE) -> EncodedChangeSet:
    size = max(1, int(chunk_size))
    manifest, groups = split_groups(change)
    chunks: list[ChangeChunk] = []
    for group_name, rows in groups.items():
        for chunk_no, start in enumerate(range(0, len(rows), size)):
            items = rows[start:start + size]
            payload = canonical_json(items)
            chunks.append(
                ChangeChunk(
                    group_name=group_name,
                    chunk_no=chunk_no,
                    items=items,
                    payload_json=payload,
                    sha256=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                )
            )
    return EncodedChangeSet(
        manifest=manifest,
        chunks=tuple(chunks),
        sha256=storage_digest(manifest, (_descriptor(chunk) for chunk in chunks)),
    )


def verify_chunk_rows(manifest: dict[str, Any], rows: Iterable[dict[str, Any]], expected_sha256: str) -> bool:
    descriptors: list[dict[str, Any]] = []
    last_by_group: dict[str, int] = {}
    for row in rows:
        group = str(row["group_name"])
        chunk_no = int(row["chunk_no"])
        expected_no = last_by_group.get(group, -1) + 1
        if chunk_no != expected_no:
            return False
        last_by_group[group] = chunk_no
        raw = row.get("payload_json")
        if not isinstance(raw, str):
            return False
        try:
            items = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return False
        if not isinstance(items, list) or len(items) != int(row["item_count"]):
            return False
        digest = hashlib.sha256(canonical_json(items).encode("utf-8")).hexdigest()
        if digest != row.get("chunk_sha256"):
            return False
        descriptors.append({
            "group": group,
            "chunk_no": chunk_no,
            "item_count": len(items),
            "sha256": digest,
        })
    return storage_digest(manifest, descriptors) == expected_sha256


def restore_group(manifest: dict[str, Any], group_name: str, chunks: Iterable[list[Any]]) -> Iterator[list[Any]]:
    """Yield stored arrays; manifest is accepted to keep the loader signature explicit."""
    del manifest, group_name
    yield from chunks
