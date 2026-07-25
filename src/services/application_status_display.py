"""Display bucketing for application status counts.

Single source of truth for turning a grouped ``{status: count}`` result (from
``RicoDB.get_application_stats`` -> ``GROUP BY status``) into the buckets Rico
shows a user in chat.

Scope — this module owns DISPLAY bucketing only:

  * which raw statuses collapse into one user-facing bucket,
  * what each bucket is called in English and Arabic,
  * that every counted row lands in exactly one bucket,
  * whether the displayed buckets reconcile against the authoritative total.

It deliberately does NOT own status ORDERING (the no-downgrade ranks in
``RicoChatAPI._get_status_rank`` and ``application_board._STATUS_RANK``) or
status VALIDATION (``applications_repo._VALID_STATUSES``). Those are separate
concerns with separate failure modes; folding them together here would couple a
label change to write-path behaviour.

The bucket set is derived from the data, not from a hardcoded list: any status
present in the grouped result gets counted, and any status with no display
mapping lands in the explicit ``unclassified`` bucket rather than being silently
dropped. The applications table stores ``status`` as unconstrained TEXT with a
``'found'`` default, so unmapped values are a live possibility, not a
hypothetical.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

UNCLASSIFIED = "unclassified"

# Raw stored status -> user-facing bucket key. Several statuses intentionally
# collapse: "opened" and "opened_external" are one thing to a user (they clicked
# through to the listing), and both are distinct from having applied.
_STATUS_TO_BUCKET: dict[str, str] = {
    "offer": "offer",
    "interview": "interview",
    "applied": "applied",
    "follow_up_due": "follow_up_due",
    "prepared": "prepared",
    "saved": "saved",
    "opened": "opened",
    "opened_external": "opened",
    "found": "found",
    "rejected": "rejected",
    "decision_made": "decision_made",
    "archived": "archived",
}

# Display order — funnel-advanced first. Ordering here is presentation only and
# carries no no-downgrade meaning.
_BUCKET_ORDER: tuple[str, ...] = (
    "offer",
    "interview",
    "applied",
    "follow_up_due",
    "prepared",
    "saved",
    "opened",
    "found",
    "rejected",
    "decision_made",
    "archived",
    UNCLASSIFIED,
)

# bucket key -> (English singular, English plural, Arabic).
# English labels are stored lowercase so a caller can render them inline
# ("194 tracked: 1 offer received, 187 links opened…") or capitalised as a
# bullet. Arabic is count-invariant here: Arabic pluralisation depends on the
# exact count in ways a two-form table cannot express, and a wrong dual/plural
# form reads worse than a neutral one.
_BUCKET_LABELS: dict[str, tuple[str, str, str]] = {
    "offer": ("offer received", "offers received", "عرض عمل"),
    "interview": ("interview stage", "interview stages", "مرحلة المقابلة"),
    "applied": ("applied", "applied", "تم التقديم"),
    "follow_up_due": ("follow-up due", "follow-ups due", "بحاجة إلى متابعة"),
    "prepared": ("prepared, not sent", "prepared, not sent", "جاهزة ولم تُرسل"),
    "saved": ("saved / to apply", "saved / to apply", "محفوظة للتقديم"),
    "opened": (
        "link opened, not applied",
        "links opened, not applied",
        "روابط فُتحت دون تقديم",
    ),
    "found": ("suggested, no action yet", "suggested, no action yet", "مقترحة دون إجراء"),
    "rejected": ("rejected", "rejected", "مرفوضة"),
    "decision_made": ("closed", "closed", "منتهية"),
    "archived": ("archived", "archived", "مؤرشفة"),
    UNCLASSIFIED: (
        "other (unrecognised status)",
        "other (unrecognised status)",
        "أخرى (حالة غير معروفة)",
    ),
}


@dataclass(frozen=True)
class Bucket:
    """One user-facing row of the pipeline breakdown."""

    key: str
    label_en: str
    label_en_plural: str
    label_ar: str
    count: int
    statuses: tuple[str, ...]

    def label(self, arabic: bool = False) -> str:
        """Count-aware label, lowercase in English for inline rendering."""
        if arabic:
            return self.label_ar
        return self.label_en if self.count == 1 else self.label_en_plural

    def bullet_label(self, arabic: bool = False) -> str:
        """Same label, capitalised for a bulleted breakdown line."""
        label = self.label(arabic)
        return label if arabic else label[:1].upper() + label[1:]


@dataclass(frozen=True)
class StatusSummary:
    """A reconciled view of one user's application status distribution."""

    total: int
    buckets: tuple[Bucket, ...]
    displayed_total: int
    reconciles: bool
    unclassified_statuses: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return self.total == 0 and self.displayed_total == 0

    def count(self, bucket_key: str) -> int:
        for bucket in self.buckets:
            if bucket.key == bucket_key:
                return bucket.count
        return 0


def _coerce_count(value: Any) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 0
    return count if count > 0 else 0


def _normalise_status(raw: Any) -> str:
    """Normalise one grouped status key.

    A NULL status column comes back from ``GROUP BY`` as ``None``; an empty or
    whitespace-only string is the same class of missing data. Both are unknown,
    not "applied" — coercing missing data to a funnel stage invents
    applications the user never made.
    """
    if raw is None:
        return ""
    return str(raw).strip().lower()


def summarize(by_status: Mapping[Any, Any] | None, total: Any = None) -> StatusSummary:
    """Build the display buckets from a grouped ``{status: count}`` result.

    ``by_status`` is the aggregation the database already performed over EVERY
    row — never a page, never a list of rows pulled into memory.

    ``total`` is the authoritative row count when the caller has one. It is
    compared against the sum of the displayed buckets rather than trusted
    blindly: if the two disagree, ``reconciles`` is False and the caller must
    say so instead of printing a confident wrong total.
    """
    counts: dict[str, int] = {}
    folded: dict[str, list[str]] = {}
    unknown: list[str] = []

    for raw_status, raw_count in (by_status or {}).items():
        count = _coerce_count(raw_count)
        if count == 0:
            continue
        status = _normalise_status(raw_status)
        bucket_key = _STATUS_TO_BUCKET.get(status, UNCLASSIFIED)
        if bucket_key == UNCLASSIFIED:
            unknown.append(status or "(no status)")
        counts[bucket_key] = counts.get(bucket_key, 0) + count
        folded.setdefault(bucket_key, []).append(status or "(no status)")

    buckets = tuple(
        Bucket(
            key=key,
            label_en=_BUCKET_LABELS[key][0],
            label_en_plural=_BUCKET_LABELS[key][1],
            label_ar=_BUCKET_LABELS[key][2],
            count=counts[key],
            statuses=tuple(sorted(folded.get(key, ()))),
        )
        for key in _BUCKET_ORDER
        if counts.get(key)
    )

    displayed_total = sum(bucket.count for bucket in buckets)
    resolved_total = _coerce_count(total) if total is not None else displayed_total

    return StatusSummary(
        total=resolved_total,
        buckets=buckets,
        displayed_total=displayed_total,
        reconciles=displayed_total == resolved_total,
        unclassified_statuses=tuple(sorted(set(unknown))),
    )


def reconciliation_note(summary: StatusSummary, arabic: bool = False) -> str:
    """Return the disclosure line for a summary whose buckets do not sum to total.

    Empty string when the summary reconciles. Both chat surfaces use this so a
    user is told the same thing about the same discrepancy.
    """
    if summary.reconciles:
        return ""
    if arabic:
        return (
            f"⚠️ لا تتطابق الأرقام: مجموع الفئات {summary.displayed_total} "
            f"بينما الإجمالي المسجَّل {summary.total}. "
            "افتح صفحة **الطلبات** للاطلاع على السجل الكامل."
        )
    return (
        f"⚠️ These numbers don't reconcile: the buckets above add up to "
        f"{summary.displayed_total}, but the recorded total is {summary.total}. "
        "Open your **Applications** page for the authoritative record."
    )
