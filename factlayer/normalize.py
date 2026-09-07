import re

def parse_value(value_str, unit_str):
    """Convert a raw value+unit into a normalized float, plus the unit it's in.
    Returns (normalized_value: float | None, normalized_unit: str | None).
    Money is normalized to INR (millions) ONLY when a currency signal is present.
    """
    if value_str is None:
        return None, None

    cleaned = value_str.replace(",", "").replace("₹", "").replace("$", "").strip()

    if "%" in cleaned or (unit_str and "%" in unit_str):
        num = _extract_number(cleaned)
        return num, "%"

    combined = f"{cleaned} {unit_str or ''}".lower()
    num = _extract_number(cleaned)
    if num is None:
        return None, unit_str

    # Only treat as currency if an actual currency signal is present.
    # Check original value_str for symbols (cleaned already stripped them).
    has_currency_symbol = bool(re.search(r"₹|\$", f"{value_str} {unit_str or ''}"))
    has_currency_word = bool(re.search(r"\brs\.?\b|\binr\b|\bcr\b|\bcrore\b|\blakh\b", combined))
    is_money = has_currency_symbol or has_currency_word

    if is_money:
        if "cr" in combined or "crore" in combined:
            return num * 10, "INR Mn"
        if "lakh" in combined:
            return num * 0.1, "INR Mn"
        if "bn" in combined or "billion" in combined:
            return num * 1000, "INR Mn"
        if "mn" in combined or "million" in combined:
            return num, "INR Mn"
        return num, "INR Mn"  # bare rupee number, no scale word

    # Not money — keep the scale word but don't attach a currency
    if "bn" in combined or "billion" in combined:
        return num * 1000, "Mn"
    return num, unit_str


def _extract_number(s):
    match = re.search(r"-?\d+\.?\d*", s)
    if not match:
        return None
    return float(match.group())


def parse_period(period_str):
    """Convert a fiscal period string into a normalized (start_date, end_date) tuple
    of ISO date strings, using India's fiscal year (Apr 1 - Mar 31).
    Returns (start: str | None, end: str | None, raw: str).
    """
    if not period_str:
        return None, None, period_str

    s = period_str.strip()

    # Q1/Q2/Q3/Q4 FY24 — MUST check before the plain FY pattern below,
    # since "FY24" alone would otherwise match inside "Q4 FY24" first.
    q_match = re.search(r"Q([1-4])\s*FY\s*'?(\d{2,4})", s, re.IGNORECASE)
    if q_match:
        q = int(q_match.group(1))
        year = _normalize_year(q_match.group(2))
        q_starts = {1: (year-1, 4), 2: (year-1, 7), 3: (year-1, 10), 4: (year, 1)}
        q_ends   = {1: (year-1, 6), 2: (year-1, 9), 3: (year-1, 12), 4: (year, 3)}
        sy, sm = q_starts[q]
        ey, em = q_ends[q]
        return f"{sy}-{sm:02d}-01", f"{ey}-{em:02d}-{_last_day(em)}", s

    # FY24, FY2024, Fiscal 2024, Fiscal Year 2024
    fy_match = re.search(r"(?:FY|Fiscal(?:\s+Year)?)\s*'?(\d{2,4})", s, re.IGNORECASE)
    if fy_match:
        year = _normalize_year(fy_match.group(1))
        return f"{year-1}-04-01", f"{year}-03-31", s

    # "as of March 31, 2024" / "March 31, 2024"
    date_match = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", s)
    if date_match:
        try:
            from datetime import datetime
            dt = datetime.strptime(f"{date_match.group(1)} {date_match.group(2)} {date_match.group(3)}", "%B %d %Y")
            iso = dt.strftime("%Y-%m-%d")
            return iso, iso, s
        except ValueError:
            pass

    return None, None, s


def _normalize_year(y):
    y = int(y)
    return y + 2000 if y < 100 else y


def _last_day(month):
    return {1: 31, 4: 30, 6: 30, 7: 31, 9: 30, 10: 31, 12: 31}.get(month, 31)


def canon_subject(subject):
    """Lowercase, strip legal suffixes, collapse whitespace — for matching, not display."""
    if not subject:
        return subject
    s = subject.strip().lower()
    s = re.sub(r"\b(limited|ltd\.?|private|pvt\.?|inc\.?|corporation|corp\.?)\b", "", s)
    s = re.sub(r"[.,]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


if __name__ == "__main__":
    tests_value = [
        ("8,142", "₹ Cr"),
        ("₹127Cr", None),
        ("81,415", "₹ Mn"),
        ("12.7", "%"),
        ("740", "Mn"),
    ]
    for v, u in tests_value:
        print(f"{v!r} {u!r} -> {parse_value(v, u)}")

    print()
    tests_period = ["FY24", "FY2024", "Q4 FY24", "Fiscal 2023", "March 31, 2024"]
    for p in tests_period:
        print(f"{p!r} -> {parse_period(p)}")

    print()
    tests_subject = ["Delhivery Limited", "Delhivery Ltd.", "DELHIVERY"]
    for s in tests_subject:
        print(f"{s!r} -> {canon_subject(s)!r}")