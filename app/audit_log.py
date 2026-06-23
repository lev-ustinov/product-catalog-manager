"""
Shared audit-log helper.

Used by category / product / xo / users routers to record changes into
the `audit_log` table. Writing an audit entry is treated as a
best-effort side-effect: if it fails (e.g. the table doesn't exist yet
because migrations haven't been applied), the main business operation
that already succeeded and was committed MUST NOT be rolled back or
fail the request — we simply log a warning and move on.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from models import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    actor: Optional[str],
    action: str,
    entity_type: str,
    entity_id: Optional[int],
    details: Optional[str] = None,
) -> None:
    """
    Append one row to audit_log and commit it in its own mini-transaction.

    Parameters
    ----------
    db          : active SQLAlchemy session (request-scoped)
    actor       : username performing the action, or "anonymous"
    action      : one of "create" | "update" | "delete" | "post" | "cancel"
    entity_type : one of "product" | "category" | "xo_instance" | "user"
    entity_id   : primary key of the affected entity (may be None)
    details     : free-form human-readable description of what changed

    This function never raises. On any error it logs a warning and
    rolls back ONLY the failed audit insert, leaving the rest of the
    session (and any previously-committed work) untouched.
    """
    try:
        db.add(AuditLog(
            user_login=(actor or "anonymous"),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
        ))
        db.commit()
    except Exception as exc:
        logger.warning(
            "Audit log write skipped (action=%s entity_type=%s entity_id=%s): %s",
            action, entity_type, entity_id, exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
