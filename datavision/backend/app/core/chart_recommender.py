"""
Chart Type Recommendation Engine — analyzes dataset column metadata and
returns the best-matching chart type with confidence, reasoning, and alternatives.

Usage:
    recommender = ChartRecommender()
    result = recommender.recommend(columns)
    # result: {"recommended_type": "line", "confidence": 0.92, "reason": "...", "alternatives": ["bar", "area"]}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Common date/time column name patterns (case-insensitive, substring match)
_DATE_PATTERNS: List[str] = [
    "date", "time", "datetime", "timestamp", "created_at", "updated_at",
    "createdat", "updatedat", "month", "year", "day", "quarter", "week",
    "dt", "occurred_at", "happened_at", "date_", "_date", "_time",
]

# Common geo / city / region column name patterns
_GEO_PATTERNS: List[str] = [
    "city", "cities", "country", "countries", "province", "state",
    "region", "district", "county", "geo", "latitude", "longitude",
    "lat", "lng", "lon", "location", "address", "postal_code",
    "zip", "zipcode", "continent", "area_code", "locale", "municipality",
]

# Data types that suggest temporal columns
_TEMPORAL_TYPES: frozenset[str] = frozenset({
    "date", "datetime", "timestamp", "time", "datetime64",
    "timestamp with time zone", "timestamp without time zone",
    "time with time zone", "time without time zone",
})

# Data types that suggest numeric / quantitative columns
_NUMERIC_TYPES: frozenset[str] = frozenset({
    "int", "integer", "bigint", "smallint", "tinyint", "mediumint",
    "decimal", "numeric", "float", "double", "real", "number",
    "int2", "int4", "int8", "float4", "float8",
    "money", "smallmoney",
})

# Data types that suggest text / string columns
_TEXT_TYPES: frozenset[str] = frozenset({
    "str", "string", "text", "varchar", "char", "nvarchar", "nchar",
    "clob", "longtext", "mediumtext", "tinytext", "character varying",
    "character", "bpchar",
})

# Data types that suggest percentage values (may also fall under numeric)
_PERCENTAGE_TYPES: frozenset[str] = frozenset({
    "percent", "percentage", "pct",
})

# Common percentage-like column names
_PERCENTAGE_PATTERNS: List[str] = [
    "percent", "percentage", "pct", "rate", "ratio", "proportion",
    "share", "market_share", "conversion_rate", "ctr", "bounce_rate",
]

# Max cardinality to treat a column as categorical (vs high-cardinality text)
_MAX_CATEGORICAL_CARDINALITY: int = 30

# Maximum cardinality to still render pie chart legibly
_MAX_PIE_CARDINALITY: int = 12

# Minimum data points to treat as "many" for area chart preference
_MANY_DATAPOINTS_THRESHOLD: int = 20

# Chart type enum
_CHART_TYPE_LABELS: Dict[str, str] = {
    "line":      "时序折线图",
    "bar":       "柱状图",
    "pie":       "饼图",
    "scatter":   "散点图",
    "area":      "面积图",
    "radar":     "雷达图",
    "map":       "地图",
    "treemap":   "矩形树图",
    "wordcloud": "词云",
    "table":     "表格",
}


# ---------------------------------------------------------------------------
# Recommendation result
# ---------------------------------------------------------------------------

@dataclass
class ChartRecommendation:
    """Structured result returned by the recommendation engine."""

    recommended_type: str       # e.g. "line", "bar", "pie"
    confidence: float           # 0.0 - 1.0
    reason: str                 # human-readable explanation
    alternatives: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_type(raw: Optional[str]) -> str:
    """Normalize a column data-type string to a stable canonical form."""
    if not raw:
        return "unknown"
    return raw.strip().lower()


def _matches_any_pattern(name: Optional[str], patterns: List[str]) -> bool:
    """Return True if `name` contains any pattern substring (case-insensitive)."""
    if not name:
        return False
    lowered = name.lower()
    return any(p.lower() in lowered for p in patterns)


def _estimate_cardinality(col: dict) -> Optional[int]:
    """Extract approximate cardinality from column metadata, if available."""
    for key in ("cardinality", "distinct_count", "unique_count", "nunique", "ndv"):
        val = col.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    # If sample values are provided, estimate from that
    sample = col.get("sample_values") or col.get("samples")
    if isinstance(sample, list) and sample:
        try:
            return len(set(sample))
        except TypeError:
            pass
    # If row count and null ratio are available but no distinct count, skip
    return None


def _estimate_row_count(col: dict) -> Optional[int]:
    """Extract row count from column metadata, if available."""
    for key in ("row_count", "total_rows", "count", "num_rows", "nrows"):
        val = col.get(key)
        if isinstance(val, (int, float)):
            return int(val)
    return None


def _is_numeric(col: dict) -> bool:
    """Check whether column is numeric by data type."""
    dtype = _normalize_type(col.get("data_type", col.get("type", "")))
    if dtype in _NUMERIC_TYPES:
        return True
    if dtype in _PERCENTAGE_TYPES:
        return True
    return False


def _is_date(col: dict) -> bool:
    """Check whether column is temporal by data type or name pattern."""
    dtype = _normalize_type(col.get("data_type", col.get("type", "")))
    if dtype in _TEMPORAL_TYPES:
        return True
    name = col.get("name", col.get("column_name", col.get("field", "")))
    if _matches_any_pattern(name, _DATE_PATTERNS):
        return True
    return False


def _is_text(col: dict) -> bool:
    """Check whether column is textual."""
    dtype = _normalize_type(col.get("data_type", col.get("type", "")))
    return dtype in _TEXT_TYPES


def _is_geo(col: dict) -> bool:
    """Check whether column represents geo / location data."""
    name = col.get("name", col.get("column_name", col.get("field", "")))
    return _matches_any_pattern(name, _GEO_PATTERNS)


def _is_percentage(col: dict) -> bool:
    """Check whether column is likely a percentage / ratio metric."""
    dtype = _normalize_type(col.get("data_type", col.get("type", "")))
    if dtype in _PERCENTAGE_TYPES:
        return True
    name = col.get("name", col.get("column_name", col.get("field", "")))
    return _matches_any_pattern(name, _PERCENTAGE_PATTERNS)


# ---------------------------------------------------------------------------
# ChartRecommender
# ---------------------------------------------------------------------------

class ChartRecommender:
    """
    Rule-based chart type recommendation engine.

    It inspects column metadata (name, data type, cardinality, semantic role)
    and scores each chart type against a set of heuristics.  The highest-scoring
    type is returned alongside a normalized confidence value, a human-readable
    reason, and a ranked list of plausible alternatives.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recommend(self, columns: List[Dict[str, Any]]) -> ChartRecommendation:
        """
        Analyze column metadata and return the best chart recommendation.

        Each dict in `columns` should contain at least:
            name / column_name / field  (str)
            data_type / type            (str)
        Optional keys that improve accuracy:
            cardinality / distinct_count  (int)
            row_count / total_rows        (int)
            is_dimension / is_metric      (bool)
            semantic_type                 (str)

        Returns a ChartRecommendation with recommended_type, confidence,
        reason, and alternatives.
        """
        if not columns:
            return ChartRecommendation(
                recommended_type="table",
                confidence=1.0,
                reason="没有提供任何列信息，无法进行图表推荐，默认使用表格展示数据。",
                alternatives=[],
            )

        # ----- classify and score -----
        cols = list(columns)
        scored = self._classify_and_score(cols)

        best_type, best_score = max(scored.items(), key=lambda kv: kv[1])

        # Collect alternatives above a minimum score threshold (excluding the winner)
        alt = sorted(
            [t for t, s in scored.items() if t != best_type and s > 0.1],
            key=lambda t: scored[t],
            reverse=True,
        )[:3]

        # Normalize confidence to 0-1 range (raw scores are heuristic)
        confidence = min(1.0, max(0.0, best_score))

        reason = self._build_reason(best_type, best_score, scored, cols)

        return ChartRecommendation(
            recommended_type=best_type,
            confidence=round(confidence, 4),
            reason=reason,
            alternatives=alt,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _best_row_count(columns: List[dict]) -> Optional[int]:
        for c in columns:
            rc = _estimate_row_count(c)
            if rc is not None:
                return rc
        # Fall back to sample length
        for c in columns:
            for key in ("sample_values", "samples"):
                val = c.get(key)
                if isinstance(val, list):
                    return len(val)
        return None

    @staticmethod
    def _col_name(col: dict) -> str:
        return col.get("name", col.get("column_name", col.get("field", ""))) or "?"

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _score_all(
        self,
        cols: List[dict],
        date_cols: List[dict],
        numeric_cols: List[dict],
        text_cols: List[dict],
        geo_cols: List[dict],
        dimension_cols: List[dict],
        metric_cols: List[dict],
        deduced_dims: List[dict],
        deduced_metrics: List[dict],
        total_rows: Optional[int],
    ) -> Dict[str, float]:

        scores: Dict[str, float] = {
            "line":      0.0,
            "bar":       0.0,
            "pie":       0.0,
            "scatter":   0.0,
            "area":      0.0,
            "radar":     0.0,
            "map":       0.0,
            "treemap":   0.0,
            "wordcloud": 0.0,
            "table":     0.1,   # table is the fallback — always slightly live
        }

        dims = dimension_cols if dimension_cols else deduced_dims
        metrics = metric_cols if metric_cols else deduced_metrics

        n_dims = len(dims)
        n_metrics = len(metrics)
        n_date = len(date_cols)
        n_numeric = len(numeric_cols)
        n_text = len(text_cols)
        n_geo = len(geo_cols)

        rows = total_rows or 0

        # 1. Date dimension + 1-3 metrics → line
        if n_date >= 1 and 1 <= n_metrics <= 3:
            scores["line"] = 0.92
            scores["area"] = 0.70
            scores["bar"] = 0.55

        # 2. 1 categorical dimension (cardinality <= 30) + 1-2 metrics → bar
        cat_dims = [d for d in dims if not _is_date(d) and self._is_categorical(d)]
        if len(cat_dims) == 1 and 1 <= n_metrics <= 2:
            scores["bar"] = max(scores["bar"], 0.88)
            scores["line"] = max(scores["line"], 0.45)
            scores["pie"] = max(scores["pie"], 0.40)

        # 3. 1 categorical dimension + 1 metric (percentage-flavored) → pie
        if len(cat_dims) == 1 and n_metrics == 1:
            pie_dim = cat_dims[0]
            card = _estimate_cardinality(pie_dim)
            if card is not None and card <= _MAX_PIE_CARDINALITY:
                # If the metric looks like a percentage, boost pie even more
                is_pct = _is_percentage(metrics[0]) if metrics else False
                scores["pie"] = max(scores["pie"], 0.90 if is_pct else 0.78)
                scores["bar"] = max(scores["bar"], 0.60)
                scores["treemap"] = max(scores["treemap"], 0.40)

        # 4. Two numeric metrics → scatter
        if n_numeric >= 2:
            # Prefer scatter when there are exactly 2 metrics and no clear dim/date
            purely_numeric = [c for c in numeric_cols if not _is_date(c)]
            if len(purely_numeric) >= 2:
                scores["scatter"] = max(scores["scatter"], 0.85)

        # 5. 1 date + 1 metric (with many data points) → area
        if n_date >= 1 and n_metrics == 1 and rows >= _MANY_DATAPOINTS_THRESHOLD:
            scores["area"] = max(scores["area"], 0.90)
            scores["line"] = max(scores["line"], 0.72)

        # 6. 3+ metrics → radar
        if n_metrics >= 3:
            scores["radar"] = max(scores["radar"], 0.82)
            scores["bar"] = max(scores["bar"], 0.40)

        # 7. Geo / 城市字段 → map
        if n_geo >= 1:
            scores["map"] = max(scores["map"], 0.88)

        # 8. 1 dimension + 1 metric (hierarchical) → treemap
        if n_dims >= 1 and n_metrics == 1:
            dim = dims[0]
            # Hierarchical hint: high cardinality dimension or "category"/"type" semantic
            card = _estimate_cardinality(dim)
            name = self._col_name(dim).lower()
            hierarchical_hint = (
                (card is not None and card > _MAX_PIE_CARDINALITY) or
                any(kw in name for kw in ("category", "type", "sector", "segment", "class", "group"))
            )
            if hierarchical_hint:
                scores["treemap"] = max(scores["treemap"], 0.80)
                scores["bar"] = max(scores["bar"], 0.45)

        # 9. Text field (word frequency) → wordcloud
        if n_text >= 1:
            # Lower priority if there are clear numeric dimensions to plot
            if n_metrics == 0 and n_date == 0:
                scores["wordcloud"] = 0.82
            elif n_text > n_numeric:
                scores["wordcloud"] = 0.55
            else:
                scores["wordcloud"] = max(scores["wordcloud"], 0.25)

        # 10. If nothing scores strongly → table
        if all(v < 0.25 for k, v in scores.items() if k != "table"):
            scores["table"] = 0.60

        return scores

    # ------------------------------------------------------------------
    # Categorical check
    # ------------------------------------------------------------------

    @staticmethod
    def _is_categorical(col: dict) -> bool:
        """A column is categorical if its cardinality is known and <= 30."""
        card = _estimate_cardinality(col)
        if card is not None:
            return card <= _MAX_CATEGORICAL_CARDINALITY
        # If no cardinality available, treat non-numeric / text columns as potentially categorical
        dtype = _normalize_type(col.get("data_type", col.get("type", "")))
        if dtype in _TEXT_TYPES:
            return True
        return False

    # ------------------------------------------------------------------
    # Reason builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_reason(
        best_type: str,
        score: float,
        scored: Dict[str, float],
        columns: List[dict],
    ) -> str:
        label = _CHART_TYPE_LABELS.get(best_type, best_type)
        # Build a brief description of what drove the decision
        date_count = sum(1 for c in columns if _is_date(c))
        numeric_count = sum(1 for c in columns if _is_numeric(c))
        text_count = sum(1 for c in columns if _is_text(c))
        geo_count = sum(1 for c in columns if _is_geo(c))
        metric_count = sum(
            1 for c in columns
            if c.get("is_metric") or _is_numeric(c)
        )
        dim_count = sum(
            1 for c in columns
            if c.get("is_dimension") or not _is_numeric(c)
        )

        total_rows = ChartRecommender._best_row_count(columns)

        reasons: Dict[str, str] = {
            "line": (
                f"检测到 {date_count} 个时间维度与 {metric_count} 个指标，"
                f"建议使用{label}展示数据随时间变化的趋势。"
            ),
            "bar": (
                f"检测到 {dim_count} 个分类维度与 {metric_count} 个指标，"
                f"建议使用{label}对比不同类别的数值大小。"
            ),
            "pie": (
                f"检测到 1 个分类维度与 1 个百分比/占比指标，"
                f"建议使用{label}展示各部分在整体中的占比关系。"
            ),
            "scatter": (
                f"检测到 {numeric_count} 个数值字段且无明显时间或分类维度，"
                f"建议使用{label}分析两个变量之间的相关性或分布规律。"
            ),
            "area": (
                f"检测到 {date_count} 个时间维度 + {metric_count} 个指标，"
                f"且数据量较大（{total_rows or '?'} 行），"
                f"建议使用{label}强调数量的累积与变化幅度。"
            ),
            "radar": (
                f"检测到 {metric_count} 个（3+）指标维度，"
                f"建议使用{label}进行多指标的综合对比分析。"
            ),
            "map": (
                f"检测到 {geo_count} 个地理/城市相关字段，"
                f"建议使用{label}将数据按地理位置可视化展示。"
            ),
            "treemap": (
                f"检测到 1 个层级维度 + 1 个指标，"
                f"建议使用{label}表示层级结构中各部分对整体的贡献。"
            ),
            "wordcloud": (
                f"检测到 {text_count} 个文本字段且缺少数值指标，"
                f"建议使用{label}展示高频关键词。"
            ),
            "table": (
                "未检测到明确的图表适配模式，建议使用表格直接展示原始数据。"
            ),
        }

        return reasons.get(best_type, f"根据列特征分析，推荐使用{label}。")

    # ------------------------------------------------------------------
    # Convenience: score a single type
    # ------------------------------------------------------------------

    def score_chart_type(self, chart_type: str, columns: List[Dict[str, Any]]) -> float:
        """Return the recommendation score for a single chart type given column metadata."""
        result = self.recommend(columns)
        # Re-run internal scoring; we don't expose the full score map publicly
        # but we can recompute internally. For simplicity we re-call recommend
        # and build a temporary scorer.  Since the recommend call is cheap
        # we just build a fresh call.
        return self._score_single(chart_type, columns)

    def _score_single(self, chart_type: str, columns: List[Dict[str, Any]]) -> float:
        if not columns:
            return 0.0
        scored = self._classify_and_score(columns)
        return round(scored.get(chart_type, 0.0), 4)

    def _classify_and_score(self, columns: List[Dict[str, Any]]) -> Dict[str, float]:
        """Shared classification + scoring path used by both recommend and _score_single."""
        cols = list(columns)
        date_cols = [c for c in cols if _is_date(c)]
        numeric_cols = [c for c in cols if _is_numeric(c)]
        text_cols = [c for c in cols if _is_text(c)]
        geo_cols = [c for c in cols if _is_geo(c)]
        dimension_cols = [
            c for c in cols
            if c.get("is_dimension") or c.get("semantic_type", "") in ("dimension", "category", "date")
        ]
        metric_cols = [
            c for c in cols
            if c.get("is_metric") or c.get("semantic_type", "") in ("metric", "measure", "value", "amount")
        ]
        deduced_dims = date_cols + [c for c in cols if not _is_numeric(c) and c not in date_cols]
        deduced_metrics = [c for c in numeric_cols if c not in date_cols]
        total_rows = self._best_row_count(cols)

        return self._score_all(
            cols=cols,
            date_cols=date_cols,
            numeric_cols=numeric_cols,
            text_cols=text_cols,
            geo_cols=geo_cols,
            dimension_cols=dimension_cols,
            metric_cols=metric_cols,
            deduced_dims=deduced_dims,
            deduced_metrics=deduced_metrics,
            total_rows=total_rows,
        )


# ---------------------------------------------------------------------------
# Convenience factory
# ---------------------------------------------------------------------------

def create_chart_recommender() -> ChartRecommender:
    """Return a pre-configured ChartRecommender instance."""
    return ChartRecommender()
