"""Execution-free inspection of the observed FM26 PKM container boundary.

This module deliberately stops at facts established by the two PKM fixtures in
the installed build. Unknown header words and record tags remain opaque.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


PKM_MARKER = b"mkp."


@dataclass(frozen=True)
class PkmString:
    offset: int
    byte_length: int
    value: str

    def as_dict(self) -> dict[str, object]:
        return {"offset": self.offset, "byte_length": self.byte_length, "value": self.value}


@dataclass(frozen=True)
class PkmCatalogueRecord:
    offset: int
    record_id: int
    value: str
    flag_a: int
    link_value: int
    flag_b: int

    def as_dict(self) -> dict[str, object]:
        return {
            "offset": self.offset,
            "record_id": self.record_id,
            "value": self.value,
            "flag_a": self.flag_a,
            "link_value": self.link_value,
            "flag_b": self.flag_b,
        }


@dataclass(frozen=True)
class PkmCatalogue:
    offset: int
    sentinel_offset: int
    records: tuple[PkmCatalogueRecord, ...]


@dataclass(frozen=True)
class PkmAdjacentStringPair:
    offset: int
    first: PkmString
    second: PkmString


@dataclass(frozen=True)
class PkmInspection:
    sha256: str
    file_size: int
    version_bytes: tuple[int, int]
    marker: str
    strings: tuple[PkmString, ...]
    catalogue: PkmCatalogue | None
    first_post_catalogue_string_pair: PkmAdjacentStringPair | None

    def as_dict(self) -> dict[str, object]:
        return {
            "sha256": self.sha256,
            "file_size": self.file_size,
            "version_bytes": list(self.version_bytes),
            "marker": self.marker,
            "length_prefixed_strings": [item.as_dict() for item in self.strings],
            "observed_catalogue": None if self.catalogue is None else {
                "offset": self.catalogue.offset,
                "sentinel_offset": self.catalogue.sentinel_offset,
                "records": [item.as_dict() for item in self.catalogue.records],
            },
            "first_post_catalogue_string_pair": (
                None if self.first_post_catalogue_string_pair is None else {
                    "offset": self.first_post_catalogue_string_pair.offset,
                    "first": self.first_post_catalogue_string_pair.first.as_dict(),
                    "second": self.first_post_catalogue_string_pair.second.as_dict(),
                }
            ),
        }


def _parse_catalogue_at(data: bytes, offset: int) -> PkmCatalogue | None:
    records: list[PkmCatalogueRecord] = []
    cursor = offset
    while cursor + 2 <= len(data):
        record_id = int.from_bytes(data[cursor:cursor + 2], "little")
        if record_id == 0xffff:
            if len(records) < 2:
                return None
            return PkmCatalogue(offset, cursor, tuple(records))
        if cursor + 6 > len(data):
            return None
        length = int.from_bytes(data[cursor + 2:cursor + 6], "little")
        end = cursor + 6 + length
        trailer_end = end + 6
        if not 1 <= length <= 1024 or trailer_end > len(data):
            return None
        try:
            value = data[cursor + 6:end].decode("utf-8")
        except UnicodeDecodeError:
            return None
        if not value or not all(char.isprintable() for char in value):
            return None
        flag_a = data[end]
        link_value = int.from_bytes(data[end + 1:end + 5], "little")
        flag_b = data[end + 5]
        if flag_a not in (0, 1) or flag_b != 1:
            return None
        records.append(PkmCatalogueRecord(
            cursor, record_id, value, flag_a, link_value, flag_b,
        ))
        cursor = trailer_end
    return None


def inspect_observed_catalogue(data: bytes) -> PkmCatalogue | None:
    """Find the repeated ID/string/metadata table present in both fixtures."""
    for offset in range(0, len(data) - 8):
        if data[offset:offset + 2] != b"\x05\x00":
            continue
        catalogue = _parse_catalogue_at(data, offset)
        if catalogue is not None:
            return catalogue
    return None


def _string_at(data: bytes, prefix_offset: int) -> PkmString | None:
    if prefix_offset + 4 > len(data):
        return None
    length = int.from_bytes(data[prefix_offset:prefix_offset + 4], "little")
    end = prefix_offset + 4 + length
    if not 1 <= length <= 1024 or end > len(data):
        return None
    try:
        value = data[prefix_offset + 4:end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not value or not all(char.isprintable() or char in "\r\n\t" for char in value):
        return None
    return PkmString(prefix_offset + 4, length, value)


def inspect_first_adjacent_string_pair(
    data: bytes, *, start_offset: int = 0,
) -> PkmAdjacentStringPair | None:
    for offset in range(start_offset, len(data) - 8):
        first = _string_at(data, offset)
        if first is None:
            continue
        second_prefix = first.offset + first.byte_length
        second = _string_at(data, second_prefix)
        if second is not None:
            return PkmAdjacentStringPair(offset, first, second)
    return None


def inspect_pkm_bytes(data: bytes, *, min_string_length: int = 4) -> PkmInspection:
    """Inventory confirmed framing without assigning meaning to opaque fields."""
    if len(data) < 8:
        raise ValueError("PKM is shorter than the observed 8-byte prefix")
    if data[2:6] != PKM_MARKER:
        raise ValueError("not an observed PKM container (missing mkp. marker)")

    strings: list[PkmString] = []
    cursor = 8
    while cursor + 4 <= len(data):
        length = int.from_bytes(data[cursor:cursor + 4], "little")
        end = cursor + 4 + length
        if min_string_length <= length <= 1024 and end <= len(data):
            raw = data[cursor + 4:end]
            try:
                value = raw.decode("utf-8")
            except UnicodeDecodeError:
                value = ""
            if value and all(char.isprintable() or char in "\r\n\t" for char in value):
                strings.append(PkmString(cursor + 4, length, value))
                cursor = end
                continue
        cursor += 1

    catalogue = inspect_observed_catalogue(data)
    pair_start = 8 if catalogue is None else catalogue.sentinel_offset + 2
    return PkmInspection(
        sha256=hashlib.sha256(data).hexdigest(),
        file_size=len(data),
        version_bytes=(data[0], data[1]),
        marker=PKM_MARKER.decode("ascii"),
        strings=tuple(strings),
        catalogue=catalogue,
        first_post_catalogue_string_pair=inspect_first_adjacent_string_pair(
            data, start_offset=pair_start,
        ),
    )


def inspect_pkm(path: str | Path, *, min_string_length: int = 4) -> PkmInspection:
    return inspect_pkm_bytes(Path(path).read_bytes(), min_string_length=min_string_length)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect observed framing in an FM26 PKM file")
    parser.add_argument("path", type=Path)
    parser.add_argument("--min-string-length", type=int, default=4)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = inspect_pkm(args.path, min_string_length=args.min_string_length)
    print(json.dumps(result.as_dict(), indent=2 if args.pretty else None, ensure_ascii=False))


if __name__ == "__main__":
    main()
