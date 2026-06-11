"""
AI 智能分析服务 - 数据洞察、图表推荐、异常检测、自动洞察

纯 Python/统计学实现，不依赖外部 LLM。
"""
import statistics
import math
import logging
from typing import Any, Optional

from app.core.chart_recommender import ChartRecommender
from app.core.anomaly_detector import AnomalyDetector

logger = logging.getLogger("datavision.ai")


# ---------------------------------------------------------------------------
# 1. 数据分析
# ---------------------------------------------------------------------------

async def analyze_data(data: list[dict]) -> dict:
    """
    对数据执行智能统计分析。

    Parameters
    ----------
    data : list[dict]
        数据行列表，每行为一个 dict。

    Returns
    -------
    dict
        {
            "summary":  {column_name: {count, mean, min, max, std, sum, median, q1, q3}},
            "trends":   [{field, direction, slope, strength, r_squared, type}],
            "anomalies": [{field, index, value, deviation_score, method}],
            "insights": [str, ...]  中文自然语言洞察
        }
    """
    if not data:
        return {
            "summary": {},
            "trends": [],
            "anomalies": [],
            "insights": ["数据为空，无法分析"],
        }

    columns = list(data[0].keys())

    # ----- 识别数值列 -----
    numeric_cols = _identify_numeric_columns(data, columns)

    # ----- 识别时间列 -----
    time_cols = _identify_time_columns(data, columns)

    # ----- 统计摘要 -----
    summary = _compute_summary(data, numeric_cols)

    # ----- 异常检测 -----
    anomalies = _detect_anomalies(data, numeric_cols)

    # ----- 趋势检测 -----
    trends = _detect_trends(data, numeric_cols, time_cols)

    # ----- 生成中文洞察 -----
    insights = _generate_insights(summary, trends, anomalies, len(data), len(columns))

    return {
        "summary": summary,
        "trends": trends,
        "anomalies": anomalies,
        "insights": insights,
    }


# ---------------------------------------------------------------------------
# 2. 图表推荐
# ---------------------------------------------------------------------------

async def recommend_chart(columns_info: list[dict], data_sample: list[dict] = None) -> dict:
    """
    根据数据特征推荐最佳图表类型。

    Parameters
    ----------
    columns_info : list[dict]
        列元数据，每项包含 name/column_name/field、data_type/type 等。
    data_sample : list[dict], optional
        数据样本行。

    Returns
    -------
    dict
        {recommended_type, confidence, reason, alternatives}
    """
    recommender = ChartRecommender()
    result = recommender.recommend(columns_info)

    # ChartRecommender.recommend 返回 ChartRecommendation dataclass，转为普通 dict
    return {
        "recommended_type": result.recommended_type,
        "confidence": result.confidence,
        "reason": result.reason,
        "alternatives": result.alternatives,
    }


# ---------------------------------------------------------------------------
# 3. 自动标题
# ---------------------------------------------------------------------------

async def auto_title(chart_config: dict) -> str:
    """
    根据图表配置自动生成有意义的中文标题。

    Parameters
    ----------
    chart_config : dict
        图表配置，至少包含 metrics 和 dimensions 字段。

    Returns
    -------
    str
        生成的中文标题。
    """
    chart_type = chart_config.get("chart_type", "")
    metrics = chart_config.get("metrics", [])
    dims = chart_config.get("dimensions", [])

    # 聚合函数中文映射
    agg_map = {
        "sum": "合计", "count": "数量", "avg": "平均",
        "max": "最大", "min": "最小", "distinct": "去重",
        "median": "中位数", "stddev": "标准差",
    }

    def _col_label(col: dict) -> str:
        """取列的显示名：优先 alias > label > display_name > field > column_name"""
        return (
            col.get("alias") or col.get("label") or col.get("display_name") or
            col.get("field") or col.get("column_name") or "数值"
        )

    def _agg_label(col: dict) -> str:
        agg = col.get("aggregation", col.get("agg", ""))
        return agg_map.get(agg, agg or "")

    # 图表类型中文名
    chart_type_map = {
        "line": "趋势图", "bar": "柱状图", "pie": "饼图",
        "scatter": "散点图", "area": "面积图", "radar": "雷达图",
        "map": "地图", "treemap": "矩形树图",
    }

    # 构建标题各部分
    parts = []

    # 维度部分
    if dims:
        dim_labels = [_col_label(d) for d in dims if _col_label(d)]
        if dim_labels:
            parts.append("各" + "、".join(dim_labels))

    # 指标部分
    if metrics:
        metric_parts = []
        for m in metrics:
            label = _col_label(m)
            agg = _agg_label(m)
            if agg:
                metric_parts.append(f"{agg}{label}")
            else:
                metric_parts.append(label)
        if metric_parts:
            parts.append("、".join(metric_parts))

    # 如果没有任何信息，给出基本标题
    if not parts:
        if dims:
            parts.append(f"各{_col_label(dims[0])}数据分布")
        elif metrics:
            parts.append(f"{_col_label(metrics[0])}概览")
        else:
            return "数据图表"

    title = "".join(parts)

    # 可选：后缀图表类型
    type_suffix = chart_type_map.get(chart_type, "")
    if type_suffix and not title.endswith(type_suffix):
        title = title + type_suffix

    return title


# ---------------------------------------------------------------------------
# 4. 智能提问建议
# ---------------------------------------------------------------------------

async def suggest_questions(dataset_columns: list[dict], sample_data: list[dict] = None) -> list[str]:
    """
    根据数据集结构生成 3-5 条自然语言提问建议（基于模板，无需 LLM）。

    Parameters
    ----------
    dataset_columns : list[dict]
        列元数据。
    sample_data : list[dict], optional
        数据样本行，用于检测数据特征。

    Returns
    -------
    list[str]
        3-5 条自然语言问题。
    """
    questions: list[str] = []

    # 分类列
    dims = [
        c for c in dataset_columns
        if c.get("is_dimension") or c.get("semantic_type") in ("dimension", "category") or
        _normalize_type(c.get("data_type", c.get("type", ""))) in (
            "string", "str", "varchar", "text", "char", "nvarchar", "nchar",
            "date", "datetime", "timestamp", "time",
        )
    ]
    metrics = [
        c for c in dataset_columns
        if c.get("is_metric") or c.get("semantic_type") in ("metric", "measure", "value", "amount") or
        _normalize_type(c.get("data_type", c.get("type", ""))) in (
            "int", "integer", "bigint", "smallint", "tinyint",
            "float", "double", "real", "decimal", "numeric", "number",
            "int2", "int4", "int8", "float4", "float8", "money",
        )
    ]

    def _label(col: dict) -> str:
        return (
            col.get("alias") or col.get("label") or col.get("display_name") or
            col.get("column_name") or col.get("field") or col.get("name", "数据")
        )

    dim_labels = [_label(d) for d in dims]
    metric_labels = [_label(m) for m in metrics]

    # 检测时间列
    time_cols = [
        d for d in dims
        if _is_time_column(d) or _is_time_column_by_name(d)
    ]

    # 检测百分比列
    pct_cols = [
        m for m in metrics
        if _looks_like_percentage(m)
    ]

    # --- 生成问题 ---

    # Q1: 维度 + 指标对比
    if dim_labels and metric_labels:
        d1 = dim_labels[0]
        m1 = metric_labels[0]
        questions.append(f"{d1}维度下，{m1}的分布情况如何？")

        if pct_cols:
            p1 = _label(pct_cols[0])
            questions.append(f"哪些{d1}的{p1}最高？最低的原因是什么？")

    # Q2: 时间趋势（如果有时间列 + 指标）
    if time_cols and metric_labels:
        t = _label(time_cols[0])
        m1 = metric_labels[0]
        questions.append(f"{m1}随时间（{t}）的变化趋势是怎样的？是否存在明显的上升或下降？")

    # Q3: 双维度交叉分析
    if len(dim_labels) >= 2 and metric_labels:
        d1, d2 = dim_labels[0], dim_labels[1]
        m1 = metric_labels[0]
        questions.append(f"{d1}和{d2}的交叉维度下，{m1}有什么差异？")

    # Q4: 排名类
    if metric_labels:
        m1 = metric_labels[0]
        if dim_labels:
            d1 = dim_labels[0]
            questions.append(f"{m1}最高的 Top 5 {d1}是哪些？")
        else:
            questions.append(f"{m1}排名前 10 的数据有什么特征？")

    # Q5: 异常/极值
    if metric_labels:
        m1 = metric_labels[0]
        questions.append(f"数据中是否存在异常值？{m1}的极值出现在什么条件下？")

    # Q6: 汇总类（补充）
    if len(metric_labels) >= 2:
        m1, m2 = metric_labels[0], metric_labels[1]
        questions.append(f"{m1}和{m2}之间是否存在相关关系？")

    # Q7: 分布形态
    if metric_labels:
        m1 = metric_labels[0]
        questions.append(f"{m1}的数据分布形态是怎样的？是否符合正态分布？")

    # 去重并限制 3-5 条
    seen: set[str] = set()
    unique: list[str] = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            unique.append(q)
    questions = unique

    # 确保至少 3 条
    if len(questions) < 3:
        fallback = [
            "整体数据概览是怎样的？各项指标表现如何？",
            "主要维度下数据分布是否均衡？",
            "核心指标的波动范围和历史趋势如何？",
        ]
        for fb in fallback:
            if fb not in seen:
                questions.append(fb)
            if len(questions) >= 5:
                break

    return questions[:5]


# ===================================================================
# 内部辅助函数
# ===================================================================

def _normalize_type(raw: Optional[str]) -> str:
    """标准化数据类型字符串。"""
    if not raw:
        return "unknown"
    return raw.strip().lower()


def _is_time_column(col: dict) -> bool:
    """根据 data_type 判断是否为时间列。"""
    dtype = _normalize_type(col.get("data_type", col.get("type", "")))
    return dtype in ("date", "datetime", "timestamp", "time", "datetime64",
                     "timestamp with time zone", "timestamp without time zone")


def _is_time_column_by_name(col: dict) -> bool:
    """根据列名判断是否为时间列。"""
    name = (col.get("name") or col.get("column_name") or
            col.get("field") or "").lower()
    time_patterns = [
        "date", "time", "datetime", "timestamp", "created_at", "updated_at",
        "createdat", "updatedat", "month", "year", "day", "quarter", "week",
        "dt", "occurred_at",
    ]
    return any(p in name for p in time_patterns)


def _looks_like_percentage(col: dict) -> bool:
    """判断是否像百分比/比率字段。"""
    name = (col.get("name") or col.get("column_name") or
            col.get("field") or "").lower()
    pct_patterns = [
        "percent", "percentage", "pct", "rate", "ratio", "proportion",
        "share", "market_share", "conversion_rate", "ctr", "bounce_rate",
    ]
    return any(p in name for p in pct_patterns)


def _identify_numeric_columns(data: list[dict], columns: list[str]) -> list[str]:
    """识别所有数值列。"""
    numeric = []
    for col in columns:
        values = []
        for row in data:
            v = row.get(col)
            if v is None:
                continue
            try:
                values.append(float(v))
            except (ValueError, TypeError):
                break
        # 至少 50% 的非空值，且至少 1 个数值
        if len(values) > 0 and len(values) >= len(data) * 0.5:
            numeric.append(col)
    return numeric


def _identify_time_columns(data: list[dict], columns: list[str]) -> list[str]:
    """识别时间序列列。检查是否可解析为日期/时间，或按行序递增。"""
    time_cols = []
    for col in columns:
        # 快速检查：如果全部为数字且单调递增，可能是时间索引
        values = []
        for row in data:
            v = row.get(col)
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    break
        if len(values) == len(data) and len(values) >= 3:
            # 检查是否单调递增
            is_increasing = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
            if is_increasing:
                time_cols.append(col)
                continue

        # 检查是否为日期字符串
        date_count = 0
        for row in data:
            v = row.get(col)
            if v and isinstance(v, str):
                # 简单日期格式检测
                if any(c in v for c in ("-", "/", "年", "月", "日", ":", "T")):
                    date_count += 1
        if date_count >= len(data) * 0.5:
            time_cols.append(col)

    # 如果没有找到时间列，将第一列视为潜在的序列列
    if not time_cols and columns:
        time_cols.append(columns[0])

    return time_cols


def _compute_summary(data: list[dict], numeric_cols: list[str]) -> dict:
    """计算数值列的完整统计摘要。"""
    summary = {}
    for col in numeric_cols:
        values = []
        for row in data:
            v = row.get(col)
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    continue
        if not values:
            continue

        n = len(values)
        total = sum(values)
        mean = total / n
        sorted_vals = sorted(values)

        # 标准差
        if n >= 2:
            variance = sum((x - mean) ** 2 for x in values) / (n - 1)
            std = round(math.sqrt(variance), 6)
        else:
            std = 0.0

        # 中位数
        mid = n // 2
        if n % 2 == 0:
            median = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        else:
            median = sorted_vals[mid]

        # Q1, Q3
        q1 = _percentile_sorted(sorted_vals, 25)
        q3 = _percentile_sorted(sorted_vals, 75)

        # 缺失值数量
        missing = len(data) - n

        summary[col] = {
            "count": n,
            "missing": missing,
            "sum": round(total, 6),
            "mean": round(mean, 6),
            "median": round(median, 6),
            "min": round(sorted_vals[0], 6),
            "max": round(sorted_vals[-1], 6),
            "std": round(std, 6),
            "q1": round(q1, 6),
            "q3": round(q3, 6),
        }

    return summary


def _percentile_sorted(sorted_vals: list[float], p: float) -> float:
    """从已排序列表中计算百分位数（线性插值）。"""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    rank = (p / 100.0) * (n - 1)
    lo = int(rank)
    hi = lo + 1
    if hi >= n:
        return sorted_vals[-1]
    frac = rank - lo
    return sorted_vals[lo] + frac * (sorted_vals[hi] - sorted_vals[lo])


def _detect_anomalies(data: list[dict], numeric_cols: list[str]) -> list[dict]:
    """对所有数值列执行异常检测。"""
    anomalies = []
    detector = AnomalyDetector()

    for col in numeric_cols[:3]:  # 限制最多 3 列以控制输出量
        values = []
        for row in data:
            v = row.get(col)
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    continue
        if len(values) < 4:
            continue

        try:
            detected = detector.detect(values, method="iqr")
        except (ValueError, TypeError) as e:
            logger.warning(f"Anomaly detection failed for column '{col}': {e}")
            continue

        for item in detected:
            if item.get("is_anomaly"):
                anomalies.append({
                    "field": col,
                    "index": item["index"],
                    "value": item["value"],
                    "deviation_score": item["deviation_score"],
                    "method": item["method"],
                })

    # 排序：偏差分数高的在前，限制总数
    anomalies.sort(key=lambda a: abs(a["deviation_score"]), reverse=True)
    return anomalies[:10]


def _detect_trends(
    data: list[dict],
    numeric_cols: list[str],
    time_cols: list[str],
) -> list[dict]:
    """
    对数值列执行趋势检测。

    使用线性回归计算斜率，同时计算 R² 评估拟合度。
    如果有时间列，会标注 time_field。
    """
    trends = []

    for col in numeric_cols[:3]:
        values = []
        for row in data:
            v = row.get(col)
            if v is not None:
                try:
                    values.append(float(v))
                except (ValueError, TypeError):
                    continue
        if len(values) < 3:
            continue

        n = len(values)
        # 线性回归: y = slope * x + intercept
        x_mean = (n - 1) / 2.0
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            continue

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # R² 计算
        ss_res = sum((values[i] - (slope * i + intercept)) ** 2 for i in range(n))
        ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # 归一化斜率（百分比形式，相对于均值）
        if abs(y_mean) > 1e-9:
            normalized_strength = round(abs(slope * n) / abs(y_mean) * 100, 2)
        else:
            normalized_strength = round(abs(slope * n), 2)

        # 判断方向
        if slope > 1e-9 and r_squared > 0.1:
            direction = "up"
        elif slope < -1e-9 and r_squared > 0.1:
            direction = "down"
        else:
            direction = "stable"

        trend_info = {
            "field": col,
            "direction": direction,
            "slope": round(slope, 6),
            "strength": normalized_strength,
            "r_squared": round(r_squared, 4),
            "type": "linear_regression",
        }

        # 如果存在时间列，标记关联
        if time_cols:
            trend_info["time_field"] = time_cols[0]

        trends.append(trend_info)

    return trends


def _generate_insights(
    summary: dict,
    trends: list,
    anomalies: list,
    total_rows: int,
    total_cols: int,
) -> list[str]:
    """基于分析结果生成中文自然语言洞察。"""
    insights: list[str] = []

    # 1. 整体概览
    insights.append(
        f"数据集共 {total_rows} 条记录、{total_cols} 个字段，"
        f"其中数值型字段 {len(summary)} 个。"
    )

    # 2. 逐字段摘要
    for col, stats in summary.items():
        if stats.get("count", 0) > 0:
            parts = [f"字段【{col}】：共 {stats['count']} 条有效记录"]
            parts.append(f"均值 {stats['mean']}")
            parts.append(f"中位数 {stats['median']}")
            parts.append(f"标准差 {stats['std']}")
            parts.append(f"范围 [{stats['min']}, {stats['max']}]")
            if stats.get("missing", 0) > 0:
                parts.append(f"缺失 {stats['missing']} 条")
            insights.append("，".join(parts))

    # 3. 趋势解读
    for t in trends:
        direction_text = {
            "up": "上升趋势",
            "down": "下降趋势",
            "stable": "保持稳定",
        }.get(t["direction"], "方向不明")

        r2 = t.get("r_squared", 0)
        if r2 >= 0.7:
            fit_text = "趋势显著"
        elif r2 >= 0.3:
            fit_text = "有一定趋势"
        else:
            fit_text = "趋势较弱"

        insight = f"字段【{t['field']}】呈{direction_text}（{fit_text}，R²={r2:.2f}）"
        if t.get("time_field"):
            insight += f"，关联时间维度【{t['time_field']}】"
        insights.append(insight)

    # 4. 异常点
    if anomalies:
        insights.append(f"检测到 {len(anomalies)} 个可能的异常数据点，建议重点关注：")
        for a in anomalies[:3]:
            insights.append(
                f"  - 字段【{a['field']}】第 {a.get('index', '?')} 行"
                f"值 = {a['value']}，偏离度 {a['deviation_score']}"
            )
    else:
        insights.append("未检测到明显异常数据点。")

    # 5. 分布特征（偏态、离散度）
    for col, stats in summary.items():
        mean_val = stats.get("mean", 0)
        median_val = stats.get("median", 0)
        std_val = stats.get("std", 0)
        if abs(mean_val) > 1e-9 and std_val > 0:
            cv = std_val / abs(mean_val)  # 变异系数
            if cv > 1.0:
                insights.append(f"字段【{col}】变异系数 {cv:.2f}，数据离散程度较高")
            elif cv < 0.1:
                insights.append(f"字段【{col}】变异系数 {cv:.2f}，数据分布较为集中")

        if abs(mean_val) > 1e-9:
            skew_hint = (mean_val - median_val) / abs(mean_val) if abs(mean_val) > 1e-9 else 0
            if abs(skew_hint) > 0.3:
                if skew_hint > 0:
                    insights.append(f"字段【{col}】均值 ({mean_val}) 明显大于中位数 ({median_val})，分布右偏")
                else:
                    insights.append(f"字段【{col}】均值 ({mean_val}) 明显小于中位数 ({median_val})，分布左偏")

    return insights
