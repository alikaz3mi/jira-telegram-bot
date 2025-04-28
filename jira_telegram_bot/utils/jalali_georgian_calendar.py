from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


@dataclass(frozen=True, slots=True)
class Day:  # ← a tiny value-object to keep the main class slim
    """Represents one calendar cell."""

    jalali: str
    gregorian: str
    hijri: str
    is_holiday: bool
    holiday_type: str

    # ─────────── convenience ───────────
    @property
    def j(self) -> int:  # terse aliases keep call-sites readable
        return int(self.jalali)

    @property
    def g(self) -> int:
        return int(self.gregorian)


class JalaliGregorianCalendar:
    """
    A lightweight façade around the raw JSON so that calling code
    never has to poke around in dictionaries.
    """

    # ─────────── constructor ───────────
    def __init__(self, month_json: Dict[str, Any]) -> None:
        self._header = month_json["header"]

        # ignore the greyed-out “disabled” padding cells
        self._days: List[Day] = [
            self._parse(day_json)
            for day_json in month_json["days"]
            if not day_json.get("disabled", False)
        ]

        # two fast look-up tables → O(1) query time
        self._by_jalali: Dict[int, Day] = {d.j: d for d in self._days}
        self._by_gregorian: Dict[int, Day] = {d.g: d for d in self._days}

    @staticmethod
    def _parse(day_json: Dict[str, Any]) -> Day:
        d, e = day_json["day"], day_json["events"]
        return Day(
            jalali=d["jalali"],
            gregorian=d["gregorian"],
            hijri=d["hijri"],
            is_holiday=e["isHoliday"],
            holiday_type=e["holidayType"].lower(),  # normalise once
        )

    # ─────────── 1. conversions ───────────
    def gregorian_from_jalali(self, jalali_day: int) -> Optional[int]:
        """Return the Gregorian day number that matches a given Jalali day."""
        day = self._by_jalali.get(jalali_day)
        return day.g if day else None

    def jalali_from_gregorian(self, gregorian_day: int) -> Optional[int]:
        """Return the Jalali day number that matches a given Gregorian day."""
        day = self._by_gregorian.get(gregorian_day)
        return day.j if day else None

    # ─────────── 2. weekend helpers ───────────
    def weekend_days(self) -> List[Day]:
        """
        Weekend identification policy:
        • If `holidayType` == "weekend" in the JSON, trust it.
        • Otherwise fall back to `is_holiday` *and* holidayType == "".
        Adjust the logic easily if your data source changes.
        """
        return [
            d
            for d in self._days
            if d.holiday_type == "weekend" or (d.is_holiday and not d.holiday_type)
        ]

    # ─────────── 3. holiday helpers ───────────
    def holidays(self) -> List[Day]:
        """All holiday cells for the month (regardless of reason)."""
        return [d for d in self._days if d.is_holiday]

    def is_holiday_gregorian(self, gregorian_day: int) -> bool:
        """True if the Gregorian **day number** is a holiday."""
        d = self._by_gregorian.get(gregorian_day)
        return bool(d and d.is_holiday)

    def is_holiday_jalali(self, jalali_day: int) -> bool:
        """True if the Jalali **day number** is a holiday."""
        d = self._by_jalali.get(jalali_day)
        return bool(d and d.is_holiday)

    # ─────────── dunder helpers ───────────
    def __repr__(self) -> str:  # nice for a quick `print(cal)`
        j, g = self._header["jalali"], self._header["gregorian"]
        return f"<Calendar {j} / {g} – {len(self._days)} days>"
