"""
动态SQL查询构建器 - 从图表配置构建MySQL SELECT语句
"""
import logging

logger = logging.getLogger("datavision.query_builder")

# 支持的聚合函数
AGGREGATIONS = {"sum": "SUM", "count": "COUNT", "avg": "AVG", "max": "MAX", "min": "MIN", "distinct": "COUNT(DISTINCT"}

# 支持的过滤运算符
OPERATORS = {"=": "=", "!=": "!=", ">": ">", "<": "<", ">=": ">=", "<=": "<=", "IN": "IN", "LIKE": "LIKE", "BETWEEN": "BETWEEN", "IS NULL": "IS NULL", "IS NOT NULL": "IS NOT NULL"}


class QueryBuilder:
    """从图表配置构建安全的参数化SQL查询"""

    @staticmethod
    def build(table_name: str, dimensions: list[dict], metrics: list[dict], filters: list[dict] = None, order_by: list[dict] = None, limit: int = 1000, offset: int = 0) -> tuple[str, dict]:
        """
        构建SQL查询和参数字典。
        返回: (sql_string, params_dict)
        """
        params = {}
        select_parts = []
        group_by_parts = []

        # SELECT 维度字段
        for dim in dimensions:
            field = dim["field"]
            alias = dim.get("alias", field)
            col = f"`{field}`"
            select_parts.append(f"{col} AS `{alias}`")
            group_by_parts.append(col)

        # SELECT 度量字段（带聚合）
        for i, metric in enumerate(metrics):
            field = metric["field"]
            agg = metric.get("aggregation", "sum").lower()
            alias = metric.get("alias", f"{agg}_{field}")
            agg_func = AGGREGATIONS.get(agg, "SUM")

            if agg == "distinct":
                col_expr = f"{agg_func} `{field}`) AS `{alias}`"
            else:
                col_expr = f"{agg_func}(`{field}`) AS `{alias}`"
            select_parts.append(col_expr)

        # FROM
        from_clause = f"FROM `{table_name}`"

        # WHERE
        where_clause = ""
        if filters:
            conditions = []
            for i, f in enumerate(filters):
                field = f["field"]
                op = f.get("operator", "=")
                value = f.get("value")

                if op in ("IS NULL", "IS NOT NULL"):
                    conditions.append(f"`{field}` {op}")
                elif op == "IN":
                    if isinstance(value, (list, tuple)):
                        placeholders = []
                        for j, v in enumerate(value):
                            pname = f"p_{i}_{j}"
                            params[pname] = v
                            placeholders.append(f":{pname}")
                        conditions.append(f"`{field}` IN ({', '.join(placeholders)})")
                elif op == "BETWEEN":
                    if isinstance(value, (list, tuple)) and len(value) == 2:
                        params[f"p_{i}_0"] = value[0]
                        params[f"p_{i}_1"] = value[1]
                        conditions.append(f"`{field}` BETWEEN :p_{i}_0 AND :p_{i}_1")
                else:
                    params[f"p_{i}"] = value
                    conditions.append(f"`{field}` {op} :p_{i}")

            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

        # GROUP BY
        group_clause = ""
        if group_by_parts:
            group_clause = "GROUP BY " + ", ".join(group_by_parts)

        # ORDER BY
        order_clause = ""
        if order_by:
            orders = []
            for ob in order_by:
                field = ob["field"]
                direction = ob.get("direction", "desc").upper()
                orders.append(f"`{field}` {direction}")
            if orders:
                order_clause = "ORDER BY " + ", ".join(orders)

        # LIMIT / OFFSET
        limit_clause = f"LIMIT {int(limit)}"
        if offset:
            limit_clause += f" OFFSET {int(offset)}"

        # 组装
        sql = "SELECT " + ", ".join(select_parts)
        sql += f" {from_clause}"
        if where_clause:
            sql += f" {where_clause}"
        if group_clause:
            sql += f" {group_clause}"
        if order_clause:
            sql += f" {order_clause}"
        sql += f" {limit_clause}"

        logger.debug("构建SQL: %s | params: %s", sql[:200], params)
        return sql, params
