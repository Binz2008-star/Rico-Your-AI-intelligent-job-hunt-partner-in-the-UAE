"""Adapters from the existing document row dictionaries into the contract.

The rows returned by the documents store, and the synthetic profile-CV record
the files surface builds, stay exactly as they are. These functions read them
and produce :class:`~src.domain.documents.inventory.DocumentRecord` values, so
a caller adopts the contract with one call instead of a rewrite.

Mapping rules, all lossless in the direction that matters (rows in, decisions
out — the row dictionary remains the caller's to return on the wire):

* ``doc_type`` -> :class:`DocumentKind` via ``DocumentKind.parse``;
* a truthy ``is_legacy`` -> ``DocumentOrigin.PROFILE_LEGACY``, which is how the
  files surface already marks the profile projection;
* a missing ``id`` yields an empty ``document_id`` rather than an error: a row
  that cannot be identified must still be counted and displayed.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from src.domain.documents.inventory import (
    DocumentInventory,
    DocumentKind,
    DocumentOrigin,
    DocumentRecord,
    build_inventory,
)

#: The id the files surface gives the synthetic profile-CV card.
PROFILE_CV_ID = "profile-cv"


def record_from_stored_row(row: Mapping[str, Any]) -> DocumentRecord:
    """Map one document row dictionary to a record."""
    origin = (
        DocumentOrigin.PROFILE_LEGACY
        if row.get("is_legacy")
        else DocumentOrigin.STORED
    )
    created_at = row.get("created_at")
    return DocumentRecord(
        document_id=str(row.get("id") or ""),
        kind=DocumentKind.parse(row.get("doc_type")),
        origin=origin,
        filename=row.get("filename") or row.get("original_filename"),
        label=row.get("label"),
        is_primary=bool(row.get("is_primary")),
        created_at=str(created_at) if created_at else None,
    )


def records_from_stored_rows(
    rows: Iterable[Mapping[str, Any]],
) -> tuple[DocumentRecord, ...]:
    """Map document rows to records, preserving their order."""
    return tuple(record_from_stored_row(row) for row in rows)


def legacy_cv_record(
    *,
    filename: Optional[str],
    created_at: Optional[str] = None,
    document_id: str = PROFILE_CV_ID,
    label: Optional[str] = None,
) -> DocumentRecord:
    """Build the profile-grounded legacy CV record.

    Whether a caller *should* build one — that is, whether the profile's CV
    grounding is settled enough to present — is not decided here. See the
    module docstring of ``src.domain.documents.inventory``.
    """
    return DocumentRecord(
        document_id=document_id,
        kind=DocumentKind.CV,
        origin=DocumentOrigin.PROFILE_LEGACY,
        filename=filename,
        label=label,
        is_primary=True,
        created_at=created_at,
    )


def inventory_from_rows(rows: Iterable[Mapping[str, Any]]) -> DocumentInventory:
    """Build an inventory straight from document row dictionaries."""
    return build_inventory(records_from_stored_rows(rows))
