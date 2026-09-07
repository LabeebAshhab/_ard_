"""Read-only guard for the query field.

A task's SQL runs against a live target database, so the GUI must not let anyone
slip in a statement that changes that database. This module splits a query field
into its individual statements (they may be separated by ';') and rejects any
statement that is not a pure read.

Two layers use it:
  * the GUI, at save time, so a bad query never even reaches the table;
  * db.run_source_query, at execution time, on top of a READ ONLY transaction,
    so a dangerous query that somehow got into the table can still never run.
"""

import re

# A statement must begin with one of these to be considered a read.
ALLOWED_START = {"SELECT", "WITH", "VALUES", "TABLE", "SHOW"}

#Filtered Queries 
FORBIDDEN = {
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER", "CREATE",
    "GRANT", "REVOKE", "MERGE", "CALL", "COPY", "EXEC", "EXECUTE", "VACUUM",
    "REINDEX", "REFRESH", "LOCK", "REPLACE", "UPSERT", "DO", "COMMENT", "SET",
    "CLUSTER", "ANALYZE", "IMPORT", "LOAD", "ATTACH", "DETACH", "PREPARE",
}


def split_statements(sql: str) -> list[str]:
    """Split on ';' while ignoring semicolons inside strings and comments.

    Blank segments (a trailing ';' or a comment-only chunk) are dropped, so up to
    a hundred statements in one field come back as a clean list.
    """
    statements: list[str] = []
    current: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":            # -- line comment
            j = sql.find("\n", i)
            if j == -1:
                current.append(sql[i:]); i = n
            else:
                current.append(sql[i:j]); i = j
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":            # /* block comment */
            j = sql.find("*/", i + 2)
            if j == -1:
                current.append(sql[i:]); i = n
            else:
                current.append(sql[i:j + 2]); i = j + 2
            continue
        if ch in ("'", '"'):                                        # string / quoted identifier
            quote = ch
            current.append(ch); i += 1
            while i < n:
                current.append(sql[i])
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:           # doubled quote escape
                        current.append(sql[i + 1]); i += 2; continue
                    i += 1; break
                i += 1
            continue
        if ch == ";":
            statements.append("".join(current)); current = []; i += 1
            continue
        current.append(ch); i += 1
    if current:
        statements.append("".join(current))
    # Drop segments that are only whitespace or comments (a trailing ';', a lone
    # comment) - they carry no statement to run or to validate.
    return [s.strip() for s in statements if _scrub(s).strip()]


def _scrub(sql: str) -> str:
    """Strip comments and the contents of string/identifier literals.

    Keyword scanning runs on the result, so a column called note holding the text
    'please update the sheet' can never be mistaken for an UPDATE statement.
    """
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "-" and i + 1 < n and sql[i + 1] == "-":
            j = sql.find("\n", i); i = n if j == -1 else j
            continue
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            j = sql.find("*/", i + 2); i = n if j == -1 else j + 2
            continue
        if ch in ("'", '"'):
            quote = ch; i += 1
            while i < n:
                if sql[i] == quote:
                    if i + 1 < n and sql[i + 1] == quote:
                        i += 2; continue
                    i += 1; break
                i += 1
            out.append(" ")
            continue
        out.append(ch); i += 1
    return "".join(out)


def _first_keyword(scrubbed: str) -> str:
    match = re.match(r"\s*([A-Za-z]+)", scrubbed)
    return match.group(1).upper() if match else ""


def check_read_only(sql: str) -> str | None:
    """Return a human-readable reason the field is not allowed, or None if it is.

    Every statement is checked - a single write anywhere in the field rejects it.
    """
    statements = split_statements(sql or "")
    if not statements:
        return "The query field is empty."

    for pos, statement in enumerate(statements, start=1):
        scrubbed = _scrub(statement)
        start = _first_keyword(scrubbed)
        if start not in ALLOWED_START:
            found = start or "an empty statement"
            return (
                f"Statement {pos} of {len(statements)} is not allowed: only read "
                f"queries (SELECT / WITH) may run against the target database, "
                f"but this one starts with {found}. Changing the target database "
                f"is blocked."
            )
        hit = next((kw for kw in FORBIDDEN
                    if re.search(rf"\b{kw}\b", scrubbed, re.IGNORECASE)), None)
        if hit:
            return (
                f"Statement {pos} of {len(statements)} is not allowed: it contains "
                f"'{hit}', which could change the target database. Only read queries "
                f"(SELECT / WITH) are permitted."
            )
    return None


def assert_read_only(sql: str) -> list[str]:
    """Raise ValueError if the field is not read-only; else return the statements."""
    problem = check_read_only(sql)
    if problem:
        raise ValueError(problem)
    return split_statements(sql)
