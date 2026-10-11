"""Structural inspection of observed FMF commentary and simulation tables.

Translation text is intentionally not returned. The inspector reports event
IDs and selector metadata needed to reproduce the boundary without copying the
game's authored strings. Numeric simulation records retain their shipped values
without assigning unproven runtime semantics.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import xml.etree.ElementTree as ET
import xml.parsers.expat
from dataclasses import asdict, dataclass
from pathlib import Path

from .managed import ManagedTacticalStyle


FMF_MARKER = b"fmf."
ZSTD_FRAME = b"\x28\xb5\x2f\xfd"


@dataclass(frozen=True)
class CommentaryStructure:
    event_count: int
    first_event_id: int
    last_event_id: int
    unique_event_ids: int
    variant_count: int
    probability_min: int
    probability_max: int
    delay_min: int
    delay_max: int


@dataclass(frozen=True)
class XgModelVersion:
    major: int
    minor: int
    release: int
    year: int


@dataclass(frozen=True)
class XgModelRecord:
    """One observed xG table record; coefficients remain exact raw integers."""

    payload_offset: int
    shot_type: str
    version: XgModelVersion
    coefficients: dict[str, int]

    def raw_linear_score(self, features: dict[str, float | int]) -> float:
        """Evaluate only the observed coefficient dot product.

        The shipped table proves the coefficient names and integers, but not
        feature transforms, fixed-point scale, link function, or model
        selection.  This deliberately returns the raw dot product and refuses
        to silently fill missing inputs; callers must supply those unresolved
        semantics explicitly.
        """
        missing = set(self.coefficients) - set(features)
        if missing:
            names = ", ".join(sorted(missing))
            raise ValueError(f"missing observed xG features: {names}")
        return float(sum(value * features[name] for name, value in self.coefficients.items()))


@dataclass(frozen=True)
class StatDistributionRecord:
    """One observed position/stat distribution table row."""

    payload_offset: int
    ability_window: tuple[float | int, float | int]
    attribute_window: tuple[float | int, float | int]
    distribution_type: str
    mean: float | int | tuple[float | int, ...]
    position: str
    stat_type: str
    variance: float | int


@dataclass(frozen=True)
class StatAttributeMapping:
    payload_offset: int
    stat_type: str
    relevant_attributes: tuple[str, ...]


@dataclass(frozen=True)
class ExpectedScoreRecord:
    """One serialized QME expected-score adjustment row."""

    payload_offset: int
    version: XgModelVersion | None
    name: str
    negative_multiplier: int
    positive_multiplier: int


@dataclass(frozen=True)
class QmeRoleRecord:
    """One serialized QME role coefficient vector."""

    payload_offset: int
    version: XgModelVersion | None
    coefficients: dict[str, int]


@dataclass(frozen=True)
class QmeRoleLookupRecord:
    payload_offset: int
    index: int
    role: int


@dataclass(frozen=True)
class QmeRevisionRecord:
    """Serialized QME revision marker preceding a table family."""

    payload_offset: int
    start_value: int
    version: XgModelVersion


@dataclass(frozen=True)
class TacticalStyleRecord:
    payload_offset: int
    record_id: int
    folder: str
    tactical_style_id: str | None
    attribute_ranges: dict[int, tuple[int, int]]
    tendency_ranges: dict[int, tuple[int, int]]
    preferred_role_ids: tuple[int, ...]

    @property
    def managed_style(self) -> ManagedTacticalStyle:
        return ManagedTacticalStyle(self.record_id)

_XG_RECORD = b"Z\x0ccoefficients"
_SHOT_TYPE = b"\x09shot_type"


def _fmf_integer(data: bytes, offset: int) -> tuple[int, int]:
    """Decode the two observed signed-integer forms in the resource stream."""
    tag = data[offset]
    if tag == 0x02:
        return struct.unpack_from("<i", data, offset + 1)[0], offset + 5
    if tag == 0x04:
        # Role lookup IDs use the observed unsigned 32-bit integer tag.
        return struct.unpack_from("<I", data, offset + 1)[0], offset + 5
    if tag == 0x05:
        # Later role lookup entries use an observed unsigned 64-bit bitmask.
        return struct.unpack_from("<Q", data, offset + 1)[0], offset + 9
    if tag & 0x0f == 0x02:
        # Inline signed values use a bias of eight in the high nibble.
        return (tag >> 4) - 8, offset + 1
    raise ValueError(f"unsupported FMF integer tag 0x{tag:02x} at {offset}")


def _fmf_string(data: bytes, offset: int) -> tuple[str, int]:
    tag = data[offset]
    if tag == 0x08:
        length = struct.unpack_from("<I", data, offset + 1)[0]
        offset += 5
    elif tag & 0x0f == 0x08:
        length = (tag >> 4) - 1
        offset += 1
    else:
        raise ValueError(f"unsupported FMF string tag 0x{tag:02x} at {offset}")
    end = offset + length
    return data[offset:end].decode("utf-8"), end


def _fmf_number(data: bytes, offset: int, *, array_item: bool = False) -> tuple[float | int, int]:
    tag = data[offset]
    if tag == 0x07:
        return struct.unpack_from("<d", data, offset + 1)[0], offset + 9
    if tag & 0x0f == 0x07:
        return float((tag >> 4) - 1), offset + 1
    # Observed all-zero ten-bin vectors use a zero byte per item.
    if array_item and tag == 0x00:
        return 0.0, offset + 1
    return _fmf_integer(data, offset)


def _fmf_numeric_value(
    data: bytes, offset: int,
) -> tuple[float | int | tuple[float | int, ...], int]:
    tag = data[offset]
    if tag & 0x0f == 0x09:
        count = (tag >> 4) - 1
        offset += 1
        values: list[float | int] = []
        for _ in range(count):
            value, offset = _fmf_number(data, offset, array_item=True)
            values.append(value)
        return tuple(values), offset
    return _fmf_number(data, offset)


def _fmf_field(data: bytes, offset: int, name: str) -> int:
    encoded = name.encode("ascii")
    if data[offset] != len(encoded) or data[offset + 1:offset + 1 + len(encoded)] != encoded:
        raise ValueError(f"expected FMF field {name!r} at {offset}")
    return offset + 1 + len(encoded)


def _fmf_count(data: bytes, offset: int) -> tuple[int, int]:
    """Decode the observed compact/long array count tags."""
    tag = data[offset]
    if tag == 0x09:
        return struct.unpack_from("<I", data, offset + 1)[0], offset + 5
    if tag & 0x0f == 0x09:
        return (tag >> 4) - 1, offset + 1
    raise ValueError(f"unsupported FMF array tag 0x{tag:02x} at {offset}")


def _fmf_version_before(data: bytes, offset: int) -> XgModelVersion | None:
    """Read the nearest enclosing serialized version marker, when present."""
    marker = b"\x07versionZ"
    start = data.rfind(marker, max(0, offset - 2048), offset)
    if start < 0:
        return None
    return _fmf_version_at(data, start)


def _fmf_version_at(data: bytes, start: int) -> XgModelVersion | None:
    marker = b"\x07versionZ"
    if data[start:start + len(marker)] != marker:
        return None
    cursor = start + len(marker)
    values: dict[str, int] = {}
    try:
        for field in ("version_major", "version_minor", "version_release", "version_year"):
            encoded = field.encode("ascii")
            if data[cursor] != len(encoded) or data[cursor + 1:cursor + 1 + len(encoded)] != encoded:
                return None
            cursor += 1 + len(encoded)
            values[field], cursor = _fmf_integer(data, cursor)
    except (IndexError, struct.error, ValueError):
        return None
    return XgModelVersion(
        values["version_major"], values["version_minor"],
        values["version_release"], values["version_year"],
    )


def _fmf_record_map(data: bytes, offset: int) -> tuple[dict[str, str | int], int]:
    """Decode an observed map with string `name` and integer/value fields."""
    tag = data[offset]
    if tag & 0x0f != 0x0a:
        raise ValueError(f"unsupported FMF map tag 0x{tag:02x} at {offset}")
    pair_count = (tag >> 4) - 1
    cursor = offset + 1
    values: dict[str, str | int] = {}
    for _ in range(pair_count):
        name_length = data[cursor]
        cursor += 1
        key = data[cursor:cursor + name_length].decode("ascii")
        cursor += name_length
        value, cursor = (_fmf_string(data, cursor) if key == "name" else _fmf_integer(data, cursor))
        values[key] = value
    return values, cursor


def inspect_xg_payload(data: bytes) -> list[XgModelRecord]:
    """Recover xG records from a decompressed observed simatch payload.

    The coefficient integers are deliberately left unscaled because neither
    their scale nor the model evaluation function is established by the FMF
    container alone.
    """
    records: list[XgModelRecord] = []
    search_from = 0
    while (start := data.find(_XG_RECORD, search_from)) >= 0:
        search_from = start + 1
        cursor = start + len(_XG_RECORD)
        map_tag = data[cursor]
        if map_tag & 0x0f != 0x0a:
            continue
        pair_count = map_tag >> 4
        cursor += 1
        coefficients: dict[str, int] = {}
        try:
            for _ in range(pair_count):
                name_length = data[cursor]
                cursor += 1
                name = data[cursor:cursor + name_length].decode("ascii")
                cursor += name_length
                value, cursor = _fmf_integer(data, cursor)
                coefficients[name] = value
            if data[cursor:cursor + len(_SHOT_TYPE)] != _SHOT_TYPE:
                continue
            shot_type, cursor = _fmf_string(data, cursor + len(_SHOT_TYPE))
            version_marker = b"\x0eversion_numberZ"
            if data[cursor:cursor + len(version_marker)] != version_marker:
                continue
            cursor += len(version_marker)
            values: dict[str, int] = {}
            for field in ("version_major", "version_minor", "version_release", "version_year"):
                encoded = field.encode("ascii")
                if data[cursor] != len(encoded) or data[cursor + 1:cursor + 1 + len(encoded)] != encoded:
                    raise ValueError(f"unexpected version field at {cursor}")
                cursor += 1 + len(encoded)
                values[field], cursor = _fmf_integer(data, cursor)
        except (IndexError, UnicodeDecodeError, struct.error, ValueError):
            continue
        records.append(XgModelRecord(
            payload_offset=start,
            shot_type=shot_type,
            version=XgModelVersion(
                values["version_major"], values["version_minor"],
                values["version_release"], values["version_year"],
            ),
            coefficients=coefficients,
        ))
    return records


def inspect_expected_score_payload(data: bytes) -> list[ExpectedScoreRecord]:
    """Recover serialized QME expected-score adjustment rows."""
    records: list[ExpectedScoreRecord] = []
    anchor = b"\x13expected_score_data"
    search_from = 0
    while (start := data.find(anchor, search_from)) >= 0:
        search_from = start + 1
        cursor = start + len(anchor)
        try:
            count, cursor = _fmf_count(data, cursor)
            for _ in range(count):
                values, cursor = _fmf_record_map(data, cursor)
                if not {
                    "name", "negative_multiplier", "positive_multiplier",
                } <= values.keys():
                    raise ValueError("incomplete expected-score record")
                name = values["name"]
                negative = values["negative_multiplier"]
                positive = values["positive_multiplier"]
                if not isinstance(name, str) or not isinstance(negative, int) or not isinstance(positive, int):
                    raise ValueError("invalid expected-score field types")
                records.append(ExpectedScoreRecord(
                    payload_offset=start, version=_fmf_version_before(data, start),
                    name=name, negative_multiplier=negative,
                    positive_multiplier=positive,
                ))
        except (IndexError, UnicodeDecodeError, struct.error, ValueError):
            continue
    return records


def inspect_qme_role_payload(data: bytes) -> list[QmeRoleRecord]:
    """Recover QME role coefficient vectors without evaluating them."""
    records: list[QmeRoleRecord] = []
    anchor = b"\trole_data"
    search_from = 0
    while (start := data.find(anchor, search_from)) >= 0:
        search_from = start + 1
        cursor = start + len(anchor)
        try:
            count, cursor = _fmf_count(data, cursor)
            for _ in range(count):
                tag = data[cursor]
                if tag & 0x0f != 0x0a or (tag >> 4) - 1 != 1:
                    raise ValueError("unexpected role-data wrapper")
                cursor += 1
                field_length = data[cursor]
                cursor += 1
                if data[cursor:cursor + field_length] != b"coefficients":
                    raise ValueError("unexpected role-data field")
                cursor += field_length
                coefficient_count, cursor = _fmf_count(data, cursor)
                coefficients: dict[str, int] = {}
                for _ in range(coefficient_count):
                    values, cursor = _fmf_record_map(data, cursor)
                    name, value = values.get("name"), values.get("value")
                    if not isinstance(name, str) or not isinstance(value, int):
                        raise ValueError("invalid role coefficient record")
                    coefficients[name] = value
                records.append(QmeRoleRecord(
                    payload_offset=start, version=_fmf_version_before(data, start),
                    coefficients=coefficients,
                ))
        except (IndexError, UnicodeDecodeError, struct.error, ValueError):
            continue
    return records


def inspect_qme_role_lookup_payload(data: bytes) -> list[QmeRoleLookupRecord]:
    """Recover serialized QME role-index to role-ID lookup rows."""
    records: list[QmeRoleLookupRecord] = []
    anchor = b"\x10role_lookup_data"
    search_from = 0
    while (start := data.find(anchor, search_from)) >= 0:
        search_from = start + 1
        cursor = start + len(anchor)
        try:
            count, cursor = _fmf_count(data, cursor)
            for _ in range(count):
                values, cursor = _fmf_record_map(data, cursor)
                index, role = values.get("index"), values.get("role")
                if not isinstance(index, int) or not isinstance(role, int):
                    raise ValueError("invalid role lookup record")
                records.append(QmeRoleLookupRecord(start, index, role))
        except (IndexError, UnicodeDecodeError, struct.error, ValueError):
            continue
    return records


def inspect_qme_revision_payload(data: bytes) -> list[QmeRevisionRecord]:
    """Recover explicit QME `start_value` and version markers."""
    records: list[QmeRevisionRecord] = []
    anchor = b"\x0bstart_value"
    search_from = 0
    while (start := data.find(anchor, search_from)) >= 0:
        search_from = start + 1
        try:
            start_value, cursor = _fmf_integer(data, start + len(anchor))
            marker = data.find(b"\x07versionZ", cursor, cursor + 64)
            if marker < 0:
                raise ValueError("revision has no adjacent version marker")
            version = _fmf_version_at(data, marker)
            if version is None:
                raise ValueError("invalid revision version marker")
        except (IndexError, struct.error, ValueError):
            continue
        records.append(QmeRevisionRecord(start, start_value, version))
    return records


def inspect_stat_distribution_payload(data: bytes) -> list[StatDistributionRecord]:
    """Recover every observed position/stat distribution row.

    This reports serialized tables only. Sampling, window interpolation and
    attribute aggregation are separate behavioral questions.
    """
    records: list[StatDistributionRecord] = []
    anchor = b"\x0eability_window"
    search_from = 0
    while (start := data.find(anchor, search_from)) >= 0:
        search_from = start + 1
        cursor = start
        try:
            cursor = _fmf_field(data, cursor, "ability_window")
            ability, cursor = _fmf_numeric_value(data, cursor)
            cursor = _fmf_field(data, cursor, "attribute_window")
            attribute, cursor = _fmf_numeric_value(data, cursor)
            cursor = _fmf_field(data, cursor, "distribution_type")
            distribution_type, cursor = _fmf_string(data, cursor)
            cursor = _fmf_field(data, cursor, "mean")
            mean, cursor = _fmf_numeric_value(data, cursor)
            cursor = _fmf_field(data, cursor, "position")
            position, cursor = _fmf_string(data, cursor)
            cursor = _fmf_field(data, cursor, "stat_type")
            stat_type, cursor = _fmf_string(data, cursor)
            cursor = _fmf_field(data, cursor, "variance")
            variance, cursor = _fmf_numeric_value(data, cursor)
            if not isinstance(ability, tuple) or len(ability) != 2:
                raise ValueError("ability_window is not an observed pair")
            if not isinstance(attribute, tuple) or len(attribute) != 2:
                raise ValueError("attribute_window is not an observed pair")
            if isinstance(variance, tuple):
                raise ValueError("variance is not an observed scalar")
            if distribution_type == "binned" and (
                not isinstance(mean, tuple) or len(mean) != 10
            ):
                raise ValueError("binned distribution does not have ten values")
            if distribution_type not in {"normal", "poisson", "binned", "zero"}:
                raise ValueError(f"unknown distribution type {distribution_type!r}")
        except (IndexError, UnicodeDecodeError, struct.error, ValueError):
            continue
        records.append(StatDistributionRecord(
            payload_offset=start,
            ability_window=ability,
            attribute_window=attribute,
            distribution_type=distribution_type,
            mean=mean,
            position=position,
            stat_type=stat_type,
            variance=variance,
        ))
    return records


def inspect_stat_attribute_payload(data: bytes) -> list[StatAttributeMapping]:
    """Recover the observed stat-to-player-attribute mapping table."""
    records: list[StatAttributeMapping] = []
    anchor = b":\x13relevant_attributes"
    search_from = 0
    while (start := data.find(anchor, search_from)) >= 0:
        search_from = start + 1
        cursor = start + len(anchor)
        try:
            list_tag = data[cursor]
            if list_tag & 0x0f != 0x09:
                continue
            count = (list_tag >> 4) - 1
            cursor += 1
            attributes: list[str] = []
            for _ in range(count):
                attribute, cursor = _fmf_string(data, cursor)
                attributes.append(attribute)
            cursor = _fmf_field(data, cursor, "stat_type")
            stat_type, cursor = _fmf_string(data, cursor)
        except (IndexError, UnicodeDecodeError, struct.error, ValueError):
            continue
        records.append(StatAttributeMapping(start, stat_type, tuple(attributes)))
    return records


def inspect_tactical_style_xml(xml: bytes, *, payload_offset: int = 0) -> list[TacticalStyleRecord]:
    """Read tactical style mechanics while excluding authored translations."""
    root = ET.fromstring(xml)
    records: list[TacticalStyleRecord] = []
    for node in root.findall("./record"):
        if "folder" not in node.attrib:
            continue

        def ranges(list_id: str) -> dict[int, tuple[int, int]]:
            result: dict[int, tuple[int, int]] = {}
            parent = node.find(f"./list[@id='{list_id}']")
            if parent is None:
                return result
            for item in parent.findall("./record"):
                low = item.find("./integer[@id='min']")
                high = item.find("./integer[@id='max']")
                if low is not None and high is not None:
                    result[int(item.attrib["id"])] = (
                        int(low.attrib["value"]), int(high.attrib["value"]),
                    )
            return result

        roles = node.find("./list[@id='preferred_roles']")
        role_ids = () if roles is None else tuple(
            int(item.attrib["value"]) for item in roles.findall("./integer")
        )
        records.append(TacticalStyleRecord(
            payload_offset=payload_offset,
            record_id=int(node.attrib["id"]),
            folder=node.attrib["folder"],
            tactical_style_id=node.attrib.get("tactical_style_id"),
            attribute_ranges=ranges("attribute_template"),
            tendency_ranges=ranges("tendency_template"),
            preferred_role_ids=role_ids,
        ))
    return records


def inspect_tactical_style_payload(data: bytes) -> list[TacticalStyleRecord]:
    child = data.find(b'<record id="0" folder="control_possession"')
    start = data.rfind(b"<record>", 0, child) if child >= 0 else -1
    if child < 0 or start < 0:
        raise ValueError("decompressed FMF payload has no observed tactical-style XML")
    return inspect_tactical_style_xml(_first_xml_document(data[start:]), payload_offset=start)


def inspect_commentary_xml(xml: bytes) -> CommentaryStructure:
    root = ET.fromstring(xml)
    events = root.find("./list[@id='evts']")
    if events is None:
        raise ValueError("XML has no observed evts list")
    ids: list[int] = []
    probabilities: list[int] = []
    delays: list[int] = []
    variants = 0
    for record in events:
        id_node = record.find("./integer[@id='id']")
        if id_node is None:
            continue
        ids.append(int(id_node.attrib["value"]))
        variant_list = record.find("./list[@id='evar']")
        if variant_list is None:
            continue
        variants += len(variant_list)
        for variant in variant_list:
            probability = variant.find("./integer[@id='prob']")
            delay = variant.find("./integer[@id='dely']")
            if probability is not None:
                probabilities.append(int(probability.attrib["value"]))
            if delay is not None:
                delays.append(int(delay.attrib["value"]))
    if not ids or not probabilities or not delays:
        raise ValueError("commentary XML is missing observed selector metadata")
    return CommentaryStructure(
        event_count=len(ids), first_event_id=min(ids), last_event_id=max(ids),
        unique_event_ids=len(set(ids)), variant_count=variants,
        probability_min=min(probabilities), probability_max=max(probabilities),
        delay_min=min(delays), delay_max=max(delays),
    )


def _first_xml_document(data: bytes) -> bytes:
    """Locate the root close without interpreting later binary FMF members."""
    parser = xml.parsers.expat.ParserCreate()
    depth = 0
    root_end: int | None = None

    def start(_name: str, _attributes: dict[str, str]) -> None:
        nonlocal depth
        depth += 1

    def end(name: str) -> None:
        nonlocal depth, root_end
        depth -= 1
        if depth == 0:
            root_end = parser.CurrentByteIndex + len(name.encode("utf-8")) + 3

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    try:
        parser.Parse(data, False)
    except xml.parsers.expat.ExpatError:
        pass
    if root_end is None:
        raise ValueError("decompressed FMF frame has no complete XML record")
    return data[:root_end]


def inspect_fmf(path: str | Path) -> CommentaryStructure:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[2:6] != FMF_MARKER:
        raise ValueError("not an observed FMF container (missing fmf. marker)")
    frame_offset = data.find(ZSTD_FRAME)
    if frame_offset < 0:
        raise ValueError("FMF has no observed Zstandard frame")
    process = subprocess.run(
        ["zstd", "-d", "-c"], input=data[frame_offset:], capture_output=True,
        check=False,
    )
    # The first frame is followed by other FMF members, so zstd may report an
    # unsupported trailing format after successfully emitting the frame.
    if not process.stdout:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return inspect_commentary_xml(_first_xml_document(process.stdout))


def inspect_xg_models(path: str | Path) -> list[XgModelRecord]:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[2:6] != FMF_MARKER:
        raise ValueError("not an observed FMF container (missing fmf. marker)")
    frame_offset = data.find(ZSTD_FRAME)
    if frame_offset < 0:
        raise ValueError("FMF has no observed Zstandard frame")
    process = subprocess.run(
        ["zstd", "-d", "-c"], input=data[frame_offset:], capture_output=True,
        check=False,
    )
    if not process.stdout:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return inspect_xg_payload(process.stdout)


def _decompress_first_fmf_frame(path: str | Path) -> bytes:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[2:6] != FMF_MARKER:
        raise ValueError("not an observed FMF container (missing fmf. marker)")
    frame_offset = data.find(ZSTD_FRAME)
    if frame_offset < 0:
        raise ValueError("FMF has no observed Zstandard frame")
    process = subprocess.run(
        ["zstd", "-d", "-c"], input=data[frame_offset:], capture_output=True,
        check=False,
    )
    if not process.stdout:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return process.stdout


def inspect_expected_scores(path: str | Path) -> list[ExpectedScoreRecord]:
    return inspect_expected_score_payload(_decompress_first_fmf_frame(path))


def inspect_qme_roles(path: str | Path) -> list[QmeRoleRecord]:
    return inspect_qme_role_payload(_decompress_first_fmf_frame(path))


def inspect_qme_role_lookup(path: str | Path) -> list[QmeRoleLookupRecord]:
    return inspect_qme_role_lookup_payload(_decompress_first_fmf_frame(path))


def inspect_qme_revisions(path: str | Path) -> list[QmeRevisionRecord]:
    return inspect_qme_revision_payload(_decompress_first_fmf_frame(path))


def inspect_stat_distributions(path: str | Path) -> list[StatDistributionRecord]:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[2:6] != FMF_MARKER:
        raise ValueError("not an observed FMF container (missing fmf. marker)")
    frame_offset = data.find(ZSTD_FRAME)
    if frame_offset < 0:
        raise ValueError("FMF has no observed Zstandard frame")
    process = subprocess.run(
        ["zstd", "-d", "-c"], input=data[frame_offset:], capture_output=True,
        check=False,
    )
    if not process.stdout:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return inspect_stat_distribution_payload(process.stdout)


def inspect_stat_attributes(path: str | Path) -> list[StatAttributeMapping]:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[2:6] != FMF_MARKER:
        raise ValueError("not an observed FMF container (missing fmf. marker)")
    frame_offset = data.find(ZSTD_FRAME)
    if frame_offset < 0:
        raise ValueError("FMF has no observed Zstandard frame")
    process = subprocess.run(
        ["zstd", "-d", "-c"], input=data[frame_offset:], capture_output=True,
        check=False,
    )
    if not process.stdout:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return inspect_stat_attribute_payload(process.stdout)


def inspect_tactical_styles(path: str | Path) -> list[TacticalStyleRecord]:
    data = Path(path).read_bytes()
    if len(data) < 8 or data[2:6] != FMF_MARKER:
        raise ValueError("not an observed FMF container (missing fmf. marker)")
    frame_offset = data.find(ZSTD_FRAME)
    if frame_offset < 0:
        raise ValueError("FMF has no observed Zstandard frame")
    process = subprocess.run(
        ["zstd", "-d", "-c"], input=data[frame_offset:], capture_output=True,
        check=False,
    )
    if not process.stdout:
        raise RuntimeError(process.stderr.decode("utf-8", errors="replace").strip())
    return inspect_tactical_style_payload(process.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect FM26 commentary selector structure")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(json.dumps(asdict(inspect_fmf(args.path)), indent=2))


if __name__ == "__main__":
    main()
