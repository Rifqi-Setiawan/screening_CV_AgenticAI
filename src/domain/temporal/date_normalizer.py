"""Date normalization module for CV temporal analysis.

Supports Indonesian and English month names/abbreviations, standard numeric
formats, year-only intervals, present/current references, and anomaly detection.
Output intervals are in absolute calendar months (year * 12 + month).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

MONTH_MAP: dict[str, int] = {
    # Indonesian & English month names and abbreviations
    "jan": 1,
    "januari": 1,
    "january": 1,
    "feb": 2,
    "peb": 2,
    "februari": 2,
    "pebruari": 2,
    "february": 2,
    "mar": 3,
    "mrt": 3,
    "maret": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "mei": 5,
    "may": 5,
    "jun": 6,
    "juni": 6,
    "june": 6,
    "jul": 7,
    "juli": 7,
    "july": 7,
    "agu": 8,
    "agt": 8,
    "ags": 8,
    "agst": 8,
    "agust": 8,
    "agustus": 8,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oct": 10,
    "oktober": 10,
    "october": 10,
    "nov": 11,
    "nop": 11,
    "november": 11,
    "nopember": 11,
    "des": 12,
    "dec": 12,
    "desember": 12,
    "december": 12,
}

PRESENT_PATTERN = re.compile(
    r"^(?:sekarang|saat\s*ini|kini|present|current|now|ongoing|masih\s*bekerja|aktif)$",
    re.IGNORECASE,
)

MAX_CAREER_MONTHS = 40 * 12  # 40 years = 480 months


def ym_to_abs_month(year: int, month: int) -> int:
    """Convert year and 1-based month to absolute month integer."""
    return year * 12 + month


def abs_month_to_ym(abs_m: int) -> tuple[int, int]:
    """Convert absolute month integer back to (year, month)."""
    year = (abs_m - 1) // 12
    month = (abs_m - 1) % 12 + 1
    return year, month


def abs_month_to_str(abs_m: int) -> str:
    """Format absolute month integer as 'YYYY-MM'."""
    y, m = abs_month_to_ym(abs_m)
    return f"{y:04d}-{m:02d}"


@dataclass
class Interval:
    """Temporal interval in absolute calendar month units (year * 12 + month).

    Attributes:
        start_lo: Earliest possible start month (pessimistic start if start_hi <= end_lo).
        start_hi: Latest possible start month.
        end_lo: Earliest possible end month.
        end_hi: Latest possible end month.
        precision: 'month' if specific month known, 'year' if year-only.
        flags: Any temporal anomaly, inference, or adjustment flags.
    """

    start_lo: int
    start_hi: int
    end_lo: int
    end_hi: int
    precision: str = "month"
    flags: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Returns False if DATE_ANOMALY is flagged."""
        return "DATE_ANOMALY" not in self.flags

    @property
    def optimistic_range(self) -> tuple[int, int] | None:
        """Widest possible active range [start_lo, end_hi]."""
        if not self.is_valid:
            return None
        return (self.start_lo, self.end_hi)

    @property
    def pessimistic_range(self) -> tuple[int, int] | None:
        """Narrowest guaranteed active range.

        If start_hi <= end_lo, range is [start_hi, end_lo].
        If start_hi > end_lo (e.g. single year '2018'), minimum guaranteed
        active duration is 1 month: [start_hi, start_hi].
        """
        if not self.is_valid:
            return None
        if self.start_hi <= self.end_lo:
            return (self.start_hi, self.end_lo)
        if self.start_lo <= self.end_hi:
            return (self.start_hi, self.start_hi)
        return None

    @property
    def optimistic_months(self) -> int:
        r = self.optimistic_range
        return (r[1] - r[0] + 1) if r else 0

    @property
    def pessimistic_months(self) -> int:
        r = self.pessimistic_range
        return (r[1] - r[0] + 1) if r else 0


@dataclass
class ParsedDatePoint:
    """Internal representation of a parsed single date endpoint."""

    month_lo: int
    month_hi: int
    precision: str
    is_present: bool = False
    inferred_year: bool = False


def _resolve_as_of(as_of: str | date | tuple[int, int] | None = None) -> tuple[int, int]:
    """Resolve as_of parameter to (year, month)."""
    if as_of is None:
        today = date.today()
        return today.year, today.month
    if isinstance(as_of, tuple) and len(as_of) == 2:
        return as_of[0], as_of[1]
    if isinstance(as_of, date):
        return as_of.year, as_of.month
    if isinstance(as_of, str):
        val = as_of.strip()
        m_iso = re.match(r"^(\d{4})-(\d{1,2})", val)
        if m_iso:
            return int(m_iso.group(1)), int(m_iso.group(2))
        try:
            d = date.fromisoformat(val)
            return d.year, d.month
        except ValueError:
            pass
    today = date.today()
    return today.year, today.month


def parse_single_date(
    raw_str: str | None,
    is_end: bool = False,
    as_of: str | date | tuple[int, int] | None = None,
) -> ParsedDatePoint | None:
    """Parse a single date endpoint string (e.g.

    'Jan 2020', '2018', 'sekarang', '03/2021').
    """
    if not raw_str or not str(raw_str).strip():
        return None

    s = str(raw_str).strip().lower()
    as_of_y, as_of_m = _resolve_as_of(as_of)
    as_of_abs = ym_to_abs_month(as_of_y, as_of_m)

    # 1. Present / Current patterns
    if PRESENT_PATTERN.match(s):
        return ParsedDatePoint(
            month_lo=as_of_abs,
            month_hi=as_of_abs,
            precision="month",
            is_present=True,
        )

    # 2. ISO / numeric: YYYY-MM or YYYY.MM or YYYY/MM
    m_ym = re.match(r"^\b(\d{4})[-/\.](\d{1,2})\b$", s)
    if m_ym:
        year = int(m_ym.group(1))
        month = int(m_ym.group(2))
        if 1 <= month <= 12:
            abs_m = ym_to_abs_month(year, month)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 3. Numeric MM/YYYY or MM-YYYY or MM.YYYY
    m_my = re.match(r"^\b(\d{1,2})[-/\.](\d{4})\b$", s)
    if m_my:
        month = int(m_my.group(1))
        year = int(m_my.group(2))
        if 1 <= month <= 12:
            abs_m = ym_to_abs_month(year, month)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 4. Full date with day: DD-MM-YYYY or DD/MM/YYYY
    m_dmy = re.match(r"^\b\d{1,2}[-/\.](\d{1,2})[-/\.](\d{4})\b$", s)
    if m_dmy:
        month = int(m_dmy.group(1))
        year = int(m_dmy.group(2))
        if 1 <= month <= 12:
            abs_m = ym_to_abs_month(year, month)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 5. Full date with day: YYYY-MM-DD
    m_ymd = re.match(r"^\b(\d{4})[-/\.](\d{1,2})[-/\.]\d{1,2}\b$", s)
    if m_ymd:
        year = int(m_ymd.group(1))
        month = int(m_ymd.group(2))
        if 1 <= month <= 12:
            abs_m = ym_to_abs_month(year, month)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 6. Day + Named month + Year: "15 Jan 2020", "15 Januari 2020"
    m_day_named = re.match(r"^\b\d{1,2}\s+([a-z]{3,9})\.?\s*['\-/\.]?\s*(\d{2,4})\b$", s)
    if m_day_named:
        month_token = m_day_named.group(1)
        year_token = m_day_named.group(2)
        month_num = MONTH_MAP.get(month_token) or MONTH_MAP.get(month_token[:3])
        if month_num:
            year_num = int(year_token)
            if year_num < 100:
                year_num += 2000 if year_num <= 50 else 1900
            abs_m = ym_to_abs_month(year_num, month_num)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 7. Named month + Year: "Jan 2020", "Agt 2022", "Mei '21", "Jul2022"
    m_named = re.match(r"^([a-z]{3,9})\.?\s*['\-/\.]?\s*(\d{2,4})$", s)
    if m_named:
        month_token = m_named.group(1)
        year_token = m_named.group(2)
        month_num = MONTH_MAP.get(month_token) or MONTH_MAP.get(month_token[:3])
        if month_num:
            year_num = int(year_token)
            if year_num < 100:
                year_num += 2000 if year_num <= 50 else 1900
            abs_m = ym_to_abs_month(year_num, month_num)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 8. Year + Named month: "2020 Jan", "2020 Januari"
    m_rev_named = re.match(r"^(\d{4})\s*['\-/\.]?\s*([a-z]{3,9})\.?$", s)
    if m_rev_named:
        year_num = int(m_rev_named.group(1))
        month_token = m_rev_named.group(2)
        month_num = MONTH_MAP.get(month_token) or MONTH_MAP.get(month_token[:3])
        if month_num:
            abs_m = ym_to_abs_month(year_num, month_num)
            return ParsedDatePoint(month_lo=abs_m, month_hi=abs_m, precision="month")

    # 9. Year only: "2018", "'18"
    m_y = re.match(r"^'?(\d{2,4})$", s)
    if m_y:
        year_num = int(m_y.group(1))
        if year_num < 100:
            year_num += 2000 if year_num <= 50 else 1900
        start_abs = ym_to_abs_month(year_num, 1)
        end_abs = ym_to_abs_month(year_num, 12)
        return ParsedDatePoint(
            month_lo=start_abs,
            month_hi=end_abs,
            precision="year",
        )

    # 10. Month only without year (e.g. in "Jan - Des 2020"):
    month_num = MONTH_MAP.get(s) or MONTH_MAP.get(s[:3])
    if month_num:
        # Placeholder month with no year known yet
        return ParsedDatePoint(
            month_lo=month_num,
            month_hi=month_num,
            precision="month_only",
            inferred_year=True,
        )

    return None


def _split_date_range_string(text: str) -> tuple[str, str] | None:
    """Split a combined date range string into (start_part, end_part)."""
    s = text.strip()

    # Range of two 4-digit years: e.g. "2018–2019", "2018-2019", "2018 - 2019"
    m_years = re.match(r"^(\d{4})\s*[-–—]\s*(\d{4})$", s)
    if m_years:
        return m_years.group(1), m_years.group(2)

    # Range of two ISO/slash dates: e.g. "2020-01 - 2021-05", "01/2020 - 05/2021"
    m_dates = re.match(
        r"^(\d{1,4}[-/\.]\d{1,4}(?:[-/\.]\d{1,4})?)\s*[-–—]\s*(\d{1,4}[-/\.]\d{1,4}(?:[-/\.]\d{1,4})?)$",
        s,
    )
    if m_dates:
        return m_dates.group(1), m_dates.group(2)

    # Word separators: s.d., s/d, sd, hingga, sampai dengan, sampai, to, until
    m_sep = re.split(
        r"\s+(?:s\.d\.|s/d|sd|hingga|sampai(?:\s+dengan)?|to|until)\s+",
        s,
        flags=re.IGNORECASE,
    )
    if len(m_sep) == 2:
        return m_sep[0].strip(), m_sep[1].strip()

    # Hyphen/dash with surrounding whitespace: "Jan 2020 - Des 2021"
    m_dash = re.split(r"\s+[-–—]\s+", s)
    if len(m_dash) == 2:
        return m_dash[0].strip(), m_dash[1].strip()

    # "Jan 2020 s.d. Sekarang" without space before/after dot
    m_sep_tight = re.split(
        r"\s*(?:\bs\.d\.|\bs/d\b|\bsd\b|\bhingga\b|\bsampai(?:\s+dengan)?\b|\bto\b|\buntil\b)\s*",
        s,
        flags=re.IGNORECASE,
    )
    if len(m_sep_tight) == 2 and m_sep_tight[0] and m_sep_tight[1]:
        return m_sep_tight[0].strip(), m_sep_tight[1].strip()

    return None


def normalize_date_range(
    raw_text: str | None = None,
    start_raw: str | None = None,
    end_raw: str | None = None,
    as_of: str | date | tuple[int, int] | None = None,
) -> Interval:
    """Normalize raw date representations into an Interval object in absolute months.

    Supports either:
      - raw_text: single combined range string (e.g. 'Jan 2020 - Des 2021', '2018–2019')
      - start_raw, end_raw: separate start and end date strings

    Detects anomalies and sets appropriate flags:
      - 'DATE_ANOMALY': end < start (>1 mo), start > as_of, duration > 40 yrs, unparseable
      - 'DATE_SWAPPED': start and end reversed by <= 1 month, swapped automatically
      - 'DATE_YEAR_ONLY_INFERRED': year-only precision used
    """
    as_of_y, as_of_m = _resolve_as_of(as_of)
    as_of_abs = ym_to_abs_month(as_of_y, as_of_m)

    s_str = start_raw
    e_str = end_raw

    # If only raw_text provided, check for split
    if (s_str is None or str(s_str).strip() == "") and raw_text:
        split_res = _split_date_range_string(raw_text)
        if split_res:
            s_str, e_str = split_res
        else:
            # Single date point or single year
            s_str = raw_text
            e_str = raw_text

    flags: list[str] = []

    # If still missing start_raw
    if not s_str or not str(s_str).strip():
        return Interval(
            start_lo=0,
            start_hi=0,
            end_lo=0,
            end_hi=0,
            precision="unknown",
            flags=["DATE_ANOMALY"],
        )

    # If end_raw missing/None, check if it's ongoing or single date
    if e_str is None or str(e_str).strip() == "":
        e_str = s_str

    parsed_start = parse_single_date(s_str, is_end=False, as_of=as_of)
    parsed_end = parse_single_date(e_str, is_end=True, as_of=as_of)

    # Handle month-only start inheriting year from end (e.g. "Jan - Des 2020")
    if parsed_start and parsed_start.precision == "month_only" and parsed_end:
        end_year = abs_month_to_ym(parsed_end.month_lo)[0]
        start_month = parsed_start.month_lo
        abs_start = ym_to_abs_month(end_year, start_month)
        parsed_start = ParsedDatePoint(
            month_lo=abs_start,
            month_hi=abs_start,
            precision="month",
        )

    if not parsed_start or not parsed_end:
        return Interval(
            start_lo=0,
            start_hi=0,
            end_lo=0,
            end_hi=0,
            precision="unknown",
            flags=["DATE_ANOMALY"],
        )

    precision = "year" if (parsed_start.precision == "year" or parsed_end.precision == "year") else "month"
    if precision == "year":
        flags.append("DATE_YEAR_ONLY_INFERRED")

    start_lo = parsed_start.month_lo
    start_hi = parsed_start.month_hi
    end_lo = parsed_end.month_lo
    end_hi = parsed_end.month_hi

    # Anomaly Check 1: start > as_of
    if start_lo > as_of_abs:
        flags.append("DATE_ANOMALY")
        return Interval(
            start_lo=start_lo,
            start_hi=start_hi,
            end_lo=end_lo,
            end_hi=end_hi,
            precision=precision,
            flags=flags,
        )

    # Anomaly Check 2: end < start
    if precision == "month":
        if end_hi < start_lo:
            diff = start_lo - end_hi
            if diff <= 1:
                # Inverted by <= 1 month: swap and flag DATE_SWAPPED
                start_lo, start_hi, end_lo, end_hi = end_lo, end_hi, start_lo, start_hi
                flags.append("DATE_SWAPPED")
            else:
                flags.append("DATE_ANOMALY")
                return Interval(
                    start_lo=start_lo,
                    start_hi=start_hi,
                    end_lo=end_lo,
                    end_hi=end_hi,
                    precision=precision,
                    flags=flags,
                )
    else:  # precision == "year"
        if end_hi < start_lo:
            flags.append("DATE_ANOMALY")
            return Interval(
                start_lo=start_lo,
                start_hi=start_hi,
                end_lo=end_lo,
                end_hi=end_hi,
                precision=precision,
                flags=flags,
            )

    # Anomaly Check 3: Career duration > 40 years (480 months)
    duration_months = end_hi - start_lo + 1
    if duration_months > MAX_CAREER_MONTHS:
        flags.append("DATE_ANOMALY")
        return Interval(
            start_lo=start_lo,
            start_hi=start_hi,
            end_lo=end_lo,
            end_hi=end_hi,
            precision=precision,
            flags=flags,
        )

    return Interval(
        start_lo=start_lo,
        start_hi=start_hi,
        end_lo=end_lo,
        end_hi=end_hi,
        precision=precision,
        flags=flags,
    )


def normalize_date_text(
    text: str,
    as_of: str | date | tuple[int, int] | None = None,
) -> Interval:
    """Convenience alias for normalize_date_range(raw_text=text)."""
    return normalize_date_range(raw_text=text, as_of=as_of)
