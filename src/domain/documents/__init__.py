"""Documents domain — the one description of what a user's documents are.

Public contract (import from here, not from the submodules):

    DocumentKind          what a document is, normalised
    DocumentOrigin        where the record came from (stored row / profile grounding)
    DocumentRecord        one document, as the product reasons about it
    DocumentInventory     the whole set, plus the decisions taken over it
    QuotaCounts           what the storage limits are counted against
    build_inventory       records -> inventory

    record_from_stored_row / records_from_stored_rows / legacy_cv_record /
    inventory_from_rows    adapters from the existing row dictionaries
"""
from src.domain.documents.adapters import (
    inventory_from_rows,
    legacy_cv_record,
    record_from_stored_row,
    records_from_stored_rows,
)
from src.domain.documents.inventory import (
    DocumentInventory,
    DocumentKind,
    DocumentOrigin,
    DocumentRecord,
    QuotaCounts,
    build_inventory,
)

__all__ = [
    "DocumentInventory",
    "DocumentKind",
    "DocumentOrigin",
    "DocumentRecord",
    "QuotaCounts",
    "build_inventory",
    "inventory_from_rows",
    "legacy_cv_record",
    "record_from_stored_row",
    "records_from_stored_rows",
]
