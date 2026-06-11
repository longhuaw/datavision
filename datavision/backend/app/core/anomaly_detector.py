"""
Data anomaly detector using basic statistical methods.

Provides two detection strategies:
  - 3-sigma rule:  values outside mean +/- 3 * std
  - IQR method:    values outside Q1 - 1.5*IQR  or  Q3 + 1.5*IQR

No heavy ML dependencies — pure stdlib + optional numpy (falls back gracefully).
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = ["AnomalyDetector"]


class AnomalyDetector:
    """Detect anomalies in a sequence of numeric values.

    Usage::

        detector = AnomalyDetector()
        results = detector.detect([1, 2, 3, 100, 4, 5], method="iqr")
        for r in results:
            if r["is_anomaly"]:
                print(r)
    """

    def __init__(self, sigma_multiplier: float = 3.0, iqr_multiplier: float = 1.5):
        """
        Parameters
        ----------
        sigma_multiplier:
            Multiplier for the 3-sigma method (default 3.0).  Use 2.0 for a
            looser threshold.
        iqr_multiplier:
            Multiplier for the IQR method (default 1.5).  Use 3.0 for "far
            out" detection.
        """
        if sigma_multiplier <= 0:
            raise ValueError("sigma_multiplier must be positive")
        if iqr_multiplier <= 0:
            raise ValueError("iqr_multiplier must be positive")

        self.sigma_multiplier = sigma_multiplier
        self.iqr_multiplier = iqr_multiplier

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def detect(self, values: list | tuple, method: str = "iqr") -> list[dict[str, Any]]:
        """Run anomaly detection on *values*.

        Parameters
        ----------
        values:
            Sequence of numeric values (int / float).  Must contain at least
            2 elements for the IQR method and at least 4 for the 3-sigma
            method (to avoid degenerate std).
        method:
            ``"sigma"`` or ``"iqr"`` (case-insensitive, default ``"iqr"``).

        Returns
        -------
        list[dict]
            Each dict has keys:
                - ``index`` (int)
                - ``value`` (int | float)
                - ``is_anomaly`` (bool)
                - ``deviation_score`` (float) — how many "units" beyond the
                  boundary.  Higher = more extreme.  0.0 = within bounds.
                - ``method`` (str)

        Raises
        ------
        ValueError
            If *values* is too short or *method* is unrecognized.
        TypeError
            If *values* contains non-numeric entries.
        """
        if not isinstance(values, (list, tuple)):
            raise TypeError("values must be a list or tuple")

        numeric = self._validate_and_convert(values)

        m = method.strip().lower()
        if m in ("sigma", "3-sigma", "three-sigma", "3sigma"):
            return self._sigma_detect(numeric)
        elif m in ("iqr", "interquartile", "tukey"):
            return self._iqr_detect(numeric)
        else:
            raise ValueError(
                f"Unknown method '{method}'.  Use 'sigma' or 'iqr'."
            )

    # ------------------------------------------------------------------
    # Stat helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_and_convert(values: list | tuple) -> list[float]:
        out: list[float] = []
        for i, v in enumerate(values):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(
                    f"Non-numeric value at index {i}: {v!r} ({type(v).__name__})"
                )
            if not math.isfinite(v):
                raise ValueError(f"Non-finite value at index {i}: {v!r}")
            out.append(float(v))
        return out

    @staticmethod
    def _mean(vals: list[float]) -> float:
        return sum(vals) / len(vals)

    @staticmethod
    def _std(vals: list[float], mean: float) -> float:
        n = len(vals)
        if n < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in vals) / (n - 1)  # sample std
        return math.sqrt(variance)

    @staticmethod
    def _percentile(vals: list[float], p: float) -> float:
        """Linear-interpolation percentile (matches numpy default)."""
        sorted_vals = sorted(vals)
        n = len(sorted_vals)
        if n == 0:
            raise ValueError("Cannot compute percentile of empty list")
        # fractional rank
        rank = (p / 100.0) * (n - 1)
        lo = int(rank)
        hi = lo + 1
        if hi >= n:
            return sorted_vals[-1]
        frac = rank - lo
        return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _sigma_detect(self, vals: list[float]) -> list[dict[str, Any]]:
        """3-sigma (or custom sigma_multiplier) detection."""
        n = len(vals)
        if n < 4:
            raise ValueError(
                f"3-sigma detection requires at least 4 values (got {n})"
            )

        mu = self._mean(vals)
        std = self._std(vals, mu)
        threshold = self.sigma_multiplier * std
        lower = mu - threshold
        upper = mu + threshold

        results: list[dict[str, Any]] = []
        for i, x in enumerate(vals):
            below = x < lower
            above = x > upper
            is_anomaly = below or above

            if is_anomaly:
                distance = (x - mu) / std if std > 0 else 0.0
                score = abs(distance) - self.sigma_multiplier
            else:
                score = 0.0

            results.append(
                {
                    "index": i,
                    "value": x,
                    "is_anomaly": is_anomaly,
                    "deviation_score": round(score, 6),
                    "method": "sigma",
                }
            )
        return results

    def _iqr_detect(self, vals: list[float]) -> list[dict[str, Any]]:
        """IQR-based (Tukey fences) detection."""
        n = len(vals)
        if n < 2:
            raise ValueError(
                f"IQR detection requires at least 2 values (got {n})"
            )

        q1 = self._percentile(vals, 25)
        q3 = self._percentile(vals, 75)
        iqr = q3 - q1
        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr

        results: list[dict[str, Any]] = []
        for i, x in enumerate(vals):
            below = x < lower
            above = x > upper
            is_anomaly = below or above

            if is_anomaly:
                # deviation in IQR units beyond the fence
                if iqr > 0:
                    if below:
                        score = (lower - x) / iqr
                    else:
                        score = (x - upper) / iqr
                else:
                    score = 0.0
            else:
                score = 0.0

            results.append(
                {
                    "index": i,
                    "value": x,
                    "is_anomaly": is_anomaly,
                    "deviation_score": round(score, 6),
                    "method": "iqr",
                }
            )
        return results
