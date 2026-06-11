"""
SQL Security Validator — parses, validates, and sanitizes user-supplied SQL.

Only SELECT statements are permitted. Dangerous keywords and multi-statement
payloads are rejected. Returns a structured result with a cleaned statement
list when validation passes.

Dependencies: sqlparse (install with `pip install sqlparse`)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

import sqlparse
from sqlparse.sql import Statement, TokenList
from sqlparse.tokens import DML, Keyword, Name


# ---------------------------------------------------------------------------
# Blocked statement types (everything except SELECT)
# ---------------------------------------------------------------------------
_FORBIDDEN_STATEMENT_TYPES: frozenset[str] = frozenset({
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
    "MERGE",
    "UPSERT",
    "LOAD",
    "CALL",
    "RENAME",
    "SET",
    "LOCK",
    "UNLOCK",
    "FLUSH",
    "OPTIMIZE",
    "ANALYZE",
    "CHECK",
    "REPAIR",
    "BACKUP",
    "RESTORE",
    "PURGE",
    "KILL",
    "SHUTDOWN",
})

# ---------------------------------------------------------------------------
# Dangerous keyword patterns that should never appear in a user query.
# Each entry is a regex applied to the *normalised* (upper-cased) SQL text.
# ---------------------------------------------------------------------------
_DANGEROUS_PATTERNS: list[re.Pattern] = [
    # File I/O
    re.compile(r"\bINTO\s+(OUTFILE|DUMPFILE)\b"),
    # Read arbitrary files from the server filesystem
    re.compile(r"\bLOAD_FILE\s*\("),
    # Resource-exhaustion / timing side-channels
    re.compile(r"\bBENCHMARK\s*\("),
    re.compile(r"\bSLEEP\s*\("),
    re.compile(r"\bWAITFOR\s+"),
    # System-level access
    re.compile(r"\bSHOW\s+(VARIABLES|STATUS|PROCESSLIST|GRANTS)\b"),
    re.compile(r"\bDESCRIBE\s+"),
    re.compile(r"\bEXPLAIN\s+"),
    # Information-schema probing as a blanket block can be too aggressive,
    # so we leave that to the caller's permission model instead.
]

# Whitelisted function names that can appear even if they are SQL keywords
# in some contexts.  Expand this list as the product needs grow.
_ALLOWED_FUNCTIONS: frozenset[str] = frozenset({
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "COALESCE",
    "IFNULL",
    "NULLIF",
    "CAST",
    "CONVERT",
    "CONCAT",
    "CONCAT_WS",
    "SUBSTRING",
    "SUBSTR",
    "TRIM",
    "UPPER",
    "LOWER",
    "LENGTH",
    "CHAR_LENGTH",
    "REPLACE",
    "LEFT",
    "RIGHT",
    "DATE_FORMAT",
    "DATEDIFF",
    "DATE_ADD",
    "DATE_SUB",
    "NOW",
    "CURDATE",
    "CURTIME",
    "UNIX_TIMESTAMP",
    "FROM_UNIXTIME",
    "YEAR",
    "MONTH",
    "DAY",
    "HOUR",
    "MINUTE",
    "SECOND",
    "ROUND",
    "FLOOR",
    "CEIL",
    "CEILING",
    "ABS",
    "MOD",
    "IF",
    "CASE",
    "GROUP_CONCAT",
    "JSON_EXTRACT",
    "JSON_UNQUOTE",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "FIRST_VALUE",
    "LAST_VALUE",
    "NTILE",
})


# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    """Returned by every validation call."""

    is_valid: bool
    error_message: Optional[str] = None
    statements: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


# ---------------------------------------------------------------------------
class SQLValidator:
    """Static-method-only class for SQL security validation."""

    @staticmethod
    def _get_statement_type(stmt: Statement) -> Optional[str]:
        """Return the DML / DDL keyword that begins *stmt*, or None."""
        for token in stmt.flatten():
            if token.ttype is DML:
                return token.value.upper()
            # Some DDL keywords are tokenised as Keyword
            if token.ttype is Keyword and token.value.upper() in {
                "CREATE", "ALTER", "DROP", "TRUNCATE", "RENAME",
                "GRANT", "REVOKE", "EXEC", "EXECUTE", "LOAD",
            }:
                return token.value.upper()
        return None

    @staticmethod
    def _contains_dangerous_patterns(normalised_sql: str) -> bool:
        """Check *normalised_sql* for any dangerous keyword pattern."""
        return any(pattern.search(normalised_sql) for pattern in _DANGEROUS_PATTERNS)

    @staticmethod
    def _extract_dangerous_match(normalised_sql: str) -> Optional[str]:
        """Return the first dangerous pattern substring found, for error messages."""
        for pattern in _DANGEROUS_PATTERNS:
            m = pattern.search(normalised_sql)
            if m:
                return m.group(0).strip()
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def validate(sql_text: str) -> ValidationResult:
        """Entry-point for SQL validation.

        Parameters
        ----------
        sql_text : str
            Raw user-supplied SQL (may be empty).

        Returns
        -------
        ValidationResult
            - *is_valid* is True only when every check passes.
            - *statements* contains the formatted SELECT statements.
            - *error_message* explains the first failure.
        """
        # 1. Reject empty input
        stripped = (sql_text or "").strip()
        if not stripped:
            return ValidationResult(False, "SQL text must not be empty.")

        # 2. Reject multi-statement payloads (semicolon inside the raw text)
        if SQLValidator._has_multiple_statements(stripped):
            return ValidationResult(
                False,
                "Multiple SQL statements are not allowed. "
                "Only a single SELECT statement may be submitted.",
            )

        # 3. Parse with sqlparse
        try:
            parsed = sqlparse.parse(stripped)
        except Exception as exc:
            return ValidationResult(False, f"SQL parsing failed: {exc}")

        if not parsed:
            return ValidationResult(False, "No valid SQL statement found.")

        # sqlparse may return multiple top-level statements; reject that too.
        if len(parsed) > 1:
            return ValidationResult(
                False,
                "Multiple SQL statements are not allowed. "
                "Only a single SELECT statement may be submitted.",
            )

        stmt = parsed[0]

        # 4. Statement-type whitelist (SELECT only)
        stmt_type = SQLValidator._get_statement_type(stmt)
        if stmt_type is None:
            return ValidationResult(
                False,
                "Could not determine the SQL statement type. "
                "Only SELECT statements are allowed.",
            )
        if stmt_type == "SELECT":
            # Good — intentionally fall through
            pass
        elif stmt_type in _FORBIDDEN_STATEMENT_TYPES:
            return ValidationResult(
                False,
                f"Statement type '{stmt_type}' is forbidden. "
                "Only SELECT statements are allowed.",
            )
        # Handle edge-case where the keyword is a recognised SQL verb not
        # explicitly listed.  Safer to reject.
        else:
            return ValidationResult(
                False,
                f"Unknown statement type '{stmt_type}'. "
                "Only SELECT statements are allowed.",
            )

        # 5. Dangerous keyword scan (run on normalised text)
        normalised = stripped.upper()
        if SQLValidator._contains_dangerous_patterns(normalised):
            match_text = SQLValidator._extract_dangerous_match(normalised)
            return ValidationResult(
                False,
                f"Dangerous keyword/pattern detected: '{match_text}'. "
                "This operation is not permitted.",
            )

        # 6. Syntactic validity: sqlparse is a parser, not a full validator,
        #    so if it returned a Statement without raising we treat it as
        #    syntactically reasonable.  We also try stripping formatting to
        #    catch gross errors (sqlparse will produce a statement even for
        #    partial input in some cases; we rely on the downstream database
        #    to be the ultimate syntax authority).

        # If sqlparse produced a statement, it is at least parseable.
        cleaned = sqlparse.format(stmt, strip_comments=True, reindent=True).strip()

        # Sanity: if the cleaned SELECT has no tokens beyond the keyword,
        # it is incomplete.
        if stmt_type == "SELECT" and not _has_substantive_tokens(stmt):
            return ValidationResult(
                False,
                "The SELECT statement contains no column or table references.",
            )

        return ValidationResult(True, statements=[cleaned])

    @staticmethod
    def is_safe(sql_text: str) -> bool:
        """Convenience: return True if the SQL passes validation."""
        return SQLValidator.validate(sql_text).is_valid

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _has_multiple_statements(raw_sql: str) -> bool:
        """Detect multiple statements by looking for unescaped semicolons.

        sqlparse itself can handle multi-statement input, but we explicitly
        reject it here.  A single trailing semicolon is stripped before
        checking so that ``SELECT 1;`` is still accepted.
        """
        text = raw_sql.strip()
        # Strip trailing semicolon (common convention)
        if text.endswith(";"):
            text = text[:-1].rstrip()
        # Look for any remaining semicolons outside string literals
        return _contains_delimiter_outside_literals(text, ";")


# ---------------------------------------------------------------------------
# Pure-function helpers (module-private)
# ---------------------------------------------------------------------------

def _contains_delimiter_outside_literals(sql: str, delimiter: str) -> bool:
    """Return True if *delimiter* appears outside single/double quotes."""
    in_single = False
    in_double = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double:
            if sql[i:i + len(delimiter)] == delimiter:
                return True
        i += 1
    return False


def _has_substantive_tokens(stmt: Statement) -> bool:
    """Return True if *stmt* contains at least one identifier or name token
    beyond the leading SELECT keyword."""
    seen_select = False
    for token in stmt.flatten():
        if token.is_whitespace:
            continue
        if token.ttype is DML and token.value.upper() == "SELECT" and not seen_select:
            seen_select = True
            continue
        # Any name, identifier, wildcard, or literal counts
        if token.ttype in (
            Name,
            Keyword,
        ) or token.value.strip() in ("*",) or _is_literal(token):
            # Keyword tokens like DISTINCT, AS, FROM, etc. are structural but
            # indicate a well-formed statement. The presence of at least one
            # Name token is the real signal.
            if token.ttype is Name:
                return True
    return False


def _is_literal(token) -> bool:
    """Best-effort check for a literal token (string, number)."""
    from sqlparse.tokens import Literal, Number

    return token.ttype in (Literal, Number)
