# Copyright (C) 2023-2026 MESH Research
#
# SPDX-License-Identifier: MIT

"""Extract Invenio subject rows from FAST MARC / MARCXML records."""

from xml.etree.ElementTree import Element

from invenio_subjects_fast.utils.facets import MARC_TAG_TO_SCHEME

MARCXML_NS = "{http://www.loc.gov/MARC21/slim}"
LABEL_SUBFIELD_CODES = ("a", "b", "c", "d", "p", "x", "z")
SPACE_JOIN_CODES = frozenset({"b", "c", "d", "p"})
DASH_JOIN_CODES = frozenset({"x", "z"})
DEPRECATED_SUFFIX = " (deprecated)"
UNLISTED_TAG = "unlisted"

# Preferred heading tag → see-from (former heading) tag used when deprecated.
PREFERRED_TO_FORMER = {
    "100": "400",
    "110": "410",
    "111": "411",
    "130": "430",
    "147": "447",
    "148": "448",
    "150": "450",
    "151": "451",
    "155": "455",
}


def build_label(subfields: list[tuple[str, str]]) -> str | None:
    """Build a FAST display label from heading subfields.

    Args:
        subfields: `(code, text)` pairs already limited to label codes.

    Returns:
        Combined label, or `None` if no usable subfield text remains.
    """
    label_fields = [(code, text) for code, text in subfields if text]
    if not label_fields:
        return None
    if len(label_fields) == 1:
        return label_fields[0][1]

    codes = [code for code, _ in label_fields]
    texts = [text for _, text in label_fields]
    if any(code in SPACE_JOIN_CODES for code in codes):
        return " ".join(texts)
    if any(code in DASH_JOIN_CODES for code in codes):
        return "--".join(texts)
    return " ".join(texts)


def make_subject_row(
    uri: str,
    scheme_suffix: str,
    label: str,
    *,
    deprecated: bool = False,
) -> dict:
    """Return one Invenio subjects vocabulary row.

    Args:
        uri: Subject id (WorldCat FAST URI).
        scheme_suffix: Scheme without the `FAST-` prefix (e.g. `topical`).
        label: Human-readable heading.
        deprecated: When true, suffix the label and set `tags: ["unlisted"]`.

    Returns:
        Dict with `id`, `scheme`, `subject`, and optionally `tags`.
    """
    subject = label
    if deprecated and not subject.endswith(DEPRECATED_SUFFIX):
        subject = f"{subject}{DEPRECATED_SUFFIX}"
    row = {
        "id": uri,
        "scheme": f"FAST-{scheme_suffix}",
        "subject": subject,
    }
    if deprecated:
        row["tags"] = [UNLISTED_TAG]
    return row


def _label_subfields_from_xml(field: Element) -> list[tuple[str, str]]:
    """Return label `(code, text)` pairs from a MARCXML datafield."""
    pairs: list[tuple[str, str]] = []
    for sub in field:
        code = sub.attrib.get("code")
        if code in LABEL_SUBFIELD_CODES and sub.text:
            pairs.append((code, sub.text))
    return pairs


def extract_from_xml_record(record: Element) -> dict | None:
    """Extract a subject row from a MARCXML `record` element.

    Args:
        record: Parsed `record` element (MARC21 slim namespace).

    Returns:
        Subject row dict, or `None` if URI / heading cannot be resolved.
    """
    ns = MARCXML_NS
    uri_parent = record.find(f"./{ns}datafield[@tag='024']")
    if uri_parent is None:
        return None
    uri_field = uri_parent.find(f"./{ns}subfield[@code='a']")
    if uri_field is None or not uri_field.text:
        return None
    uri = uri_field.text

    leader_el = record.find(f"./{ns}leader")
    leader = leader_el.text if leader_el is not None and leader_el.text else ""
    deleted = len(leader) > 5 and leader[5] == "d"

    preferred = None
    for field in record.findall(f"./{ns}datafield"):
        tag = field.attrib.get("tag")
        if tag in MARC_TAG_TO_SCHEME:
            preferred = field
            break

    marc_tag: str | None = None
    label: str | None = None
    if preferred is not None:
        marc_tag = preferred.attrib.get("tag")
        label = build_label(_label_subfields_from_xml(preferred))

    deprecated = deleted or not label
    if not label and marc_tag:
        former_tag = PREFERRED_TO_FORMER.get(marc_tag)
        if former_tag:
            former = record.find(f"./{ns}datafield[@tag='{former_tag}']")
            if former is not None:
                label = build_label(_label_subfields_from_xml(former))
    if not label:
        for former_tag in PREFERRED_TO_FORMER.values():
            former = record.find(f"./{ns}datafield[@tag='{former_tag}']")
            if former is None:
                continue
            label = build_label(_label_subfields_from_xml(former))
            if label:
                # Infer scheme from the see-from tag's preferred counterpart.
                for pref, form in PREFERRED_TO_FORMER.items():
                    if form == former_tag and pref in MARC_TAG_TO_SCHEME:
                        marc_tag = pref
                        break
                break

    if not label or marc_tag not in MARC_TAG_TO_SCHEME:
        return None

    return make_subject_row(
        uri,
        MARC_TAG_TO_SCHEME[marc_tag],
        label,
        deprecated=deprecated,
    )


def _label_subfields_from_marc(field) -> list[tuple[str, str]]:
    """Return label `(code, text)` pairs from a pymarc Field."""
    pairs: list[tuple[str, str]] = []
    for sub in field.subfields:
        if sub.code in LABEL_SUBFIELD_CODES and sub.value:
            pairs.append((sub.code, sub.value))
    return pairs


def extract_from_marc_record(record) -> dict | None:
    """Extract a subject row from a pymarc `Record`.

    Args:
        record: Binary MARC record (pymarc).

    Returns:
        Subject row dict, or `None` if URI / heading cannot be resolved.
    """
    field_024 = record["024"]
    if field_024 is None or not field_024.get("a"):
        return None
    uri = field_024["a"]

    leader = str(record.leader or "")
    deleted = len(leader) > 5 and leader[5] == "d"

    preferred = None
    marc_tag: str | None = None
    for tag in MARC_TAG_TO_SCHEME:
        fields = record.get_fields(tag)
        if fields:
            preferred = fields[0]
            marc_tag = tag
            break

    label: str | None = None
    if preferred is not None:
        label = build_label(_label_subfields_from_marc(preferred))

    deprecated = deleted or not label
    if not label and marc_tag:
        former_tag = PREFERRED_TO_FORMER.get(marc_tag)
        if former_tag:
            former_fields = record.get_fields(former_tag)
            if former_fields:
                label = build_label(_label_subfields_from_marc(former_fields[0]))
    if not label:
        for pref, former_tag in PREFERRED_TO_FORMER.items():
            former_fields = record.get_fields(former_tag)
            if not former_fields:
                continue
            label = build_label(_label_subfields_from_marc(former_fields[0]))
            if label:
                marc_tag = pref
                break

    if not label or marc_tag not in MARC_TAG_TO_SCHEME:
        return None

    return make_subject_row(
        uri,
        MARC_TAG_TO_SCHEME[marc_tag],
        label,
        deprecated=deprecated,
    )
