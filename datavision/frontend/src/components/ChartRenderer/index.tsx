/**
 * ChartRenderer - 核心图表渲染组件
 *
 * 被 ChartWorkbench 和 Designer 复用。
 * 负责根据 chartType / data / styleConfig 渲染不同图表形态。
 *
 * 支持的 chartType：
 *   line | bar | pie | scatter | area | heatmap | radar | funnel | gauge
 *   | treemap | table | card
 *
 * table → Antd Table
 * card  → Antd Statistic (单值指标卡)
 * 其余  → ECharts (via echarts-for-react core + 按需注册组件)
 */

import React, { useMemo } from 'react';
import { Spin, Empty, Table, Card, Statistic } from 'antd';

// ==================== ECharts 按需引入 (tree-shaking) ====================
import * as echarts from 'echarts/core';
import { LineChart, BarChart, PieChart, ScatterChart, RadarChart, FunnelChart, GaugeChart, TreemapChart, HeatmapChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent, ToolboxComponent, DataZoomComponent, VisualMapComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import ReactEChartsCore from 'echarts-for-react/lib/core';

import type { EChartsOption } from 'echarts';
import type { ChartType, ChartStyleConfig } from '@/types';

// 注册所有需要的 ECharts 组件（只注册一次）
echarts.use([
  // 图表类型
  LineChart,
  BarChart,
  PieChart,
  ScatterChart,
  RadarChart,
  FunnelChart,
  GaugeChart,
  TreemapChart,
  HeatmapChart,
  // 组件
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  DataZoomComponent,
  VisualMapComponent,
  // 渲染器
  CanvasRenderer,
]);

// ==================== Props ====================

export interface ChartRendererProps {
  /** 图表类型 */
  chartType: ChartType;
  /** 图表数据：列名 + 行数据 */
  data: {
    columns: string[];
    rows: Record<string, unknown>[];
  };
  /** 样式配置（可选） */
  styleConfig?: ChartStyleConfig | null;
  /** 容器高度，默认 400 */
  height?: number | string;
  /** 加载态 */
  loading?: boolean;
}

// ==================== 默认配色 ====================

const DEFAULT_COLORS = [
  '#1677ff',
  '#52c41a',
  '#faad14',
  '#f5222d',
  '#722ed1',
  '#13c2c2',
  '#eb2f96',
  '#fa8c16',
  '#a0d911',
  '#2f54eb',
];

// ==================== Helper: 自动检测维度 / 度量列 ====================

/**
 * 根据第一行数据类型将列分为"维度（字符串）"与"度量（数值）"。
 * - 首个字符串列 → 默认 xAxis / name 字段
 * - 首个数值列   → 默认 yAxis / value 字段
 */
function detectColumns(
  columns: string[],
  rows: Record<string, unknown>[],
): { dims: string[]; metrics: string[]; xCol: string; yCol: string } {
  const firstRow = rows[0] ?? {};
  const dims: string[] = [];
  const metrics: string[] = [];

  for (const col of columns) {
    const val = firstRow[col];
    if (typeof val === 'string' || val instanceof Date) {
      dims.push(col);
    } else if (typeof val === 'number' || typeof val === 'bigint') {
      metrics.push(col);
    }
  }

  const xCol = dims[0] || columns[0];
  const yCol = metrics[0] || columns[columns.length - 1];

  return { dims, metrics, xCol, yCol };
}

// ==================== Helper: 提取样式 ====================

interface ResolvedStyle {
  title?: { text?: string; show?: boolean; fontSize?: number };
  colors: string[];
  legend: { show: boolean; position: string };
  tooltip: { show: boolean };
  animation: { enabled: boolean; duration: number };
}

function resolveStyle(raw?: ChartStyleConfig | null): ResolvedStyle {
  return {
    title: raw?.title
      ? { text: raw.title.text, show: raw.title.show !== false, fontSize: raw.title.fontSize ?? 16 }
      : undefined,
    colors: raw?.colors?.length ? raw.colors : DEFAULT_COLORS,
    legend: {
      show: raw?.legend?.show !== false,
      position: raw?.legend?.position ?? 'bottom',
    },
    tooltip: {
      show: raw?.tooltip?.show !== false,
    },
    animation: {
      enabled: raw?.animation?.enabled !== false,
      duration: raw?.animation?.duration ?? 800,
    },
  };
}

// ==================== 核心：buildEChartsOption ====================

function buildEChartsOption(
  chartType: ChartType,
  data: ChartRendererProps['data'],
  style: ResolvedStyle,
): EChartsOption {
  const { columns, rows } = data;
  const { dims, metrics, xCol, yCol } = detectColumns(columns, rows);

  // x 轴维度值
  const xData = rows.map((r) => String(r[xCol] ?? ''));

  // 布局 legend 的 top / bottom / left / orient
  const legendPosition = style.legend.position;
  const legendOrient =
    legendPosition === 'left' || legendPosition === 'right' ? 'vertical' : 'horizontal';
  const legendConfig: EChartsOption['legend'] =
    style.legend.show && legendPosition
      ? {
          show: true,
          orient: legendOrient,
          left: legendPosition === 'left' ? 0 : legendPosition === 'right' ? 'right' : 'center',
          top: legendPosition === 'top' ? 0 : undefined,
          bottom: legendPosition === 'bottom' ? 0 : undefined,
        }
      : { show: false };

  // 公共 base option
  const base: EChartsOption = {
    color: style.colors,
    tooltip: {
      show: style.tooltip.show,
      trigger: chartType === 'pie' ? 'item' : 'axis',
    },
    legend: legendConfig,
    animation: style.animation.enabled,
    animationDuration: style.animation.duration,
  };

  if (style.title?.show && style.title?.text) {
    base.title = {
      text: style.title.text,
      left: 'center',
      textStyle: { fontSize: style.title.fontSize ?? 16 },
    };
  }

  // ==================== 各图表类型 ====================

  switch (chartType) {
    // -------- 折线 / 柱状 / 面积 (笛卡尔坐标系) --------
    case 'line':
    case 'bar':
    case 'area': {
      const isArea = chartType === 'area';
      const seriesCols = metrics.length > 0 ? metrics : [columns[columns.length - 1]];

      const series = seriesCols.map((col) => ({
        name: col,
        type: isArea ? 'line' : chartType,
        data: rows.map((r) => Number(r[col]) || 0),
        smooth: chartType === 'line' || isArea,
        areaStyle: isArea ? { opacity: 0.3 } : undefined,
        ...(chartType === 'bar' ? { barMaxWidth: 40 } : {}),
      }));

      return {
        ...base,
        xAxis: {
          type: 'category',
          data: xData,
          axisLabel: { rotate: xData.length > 8 ? 30 : 0 },
        },
        yAxis: { type: 'value' },
        legend: { ...base.legend, data: seriesCols },
        series,
      };
    }

    // -------- 饼图 --------
    case 'pie': {
      const pieData = rows.map((r) => ({
        name: String(r[xCol] ?? ''),
        value: Number(r[yCol]) || 0,
      }));
      return {
        ...base,
        series: [
          {
            type: 'pie',
            radius: ['40%', '68%'],
            center: ['50%', '50%'],
            data: pieData,
            label: { show: true, formatter: '{b}: {d}%' },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowOffsetX: 0,
                shadowColor: 'rgba(0,0,0,0.5)',
              },
            },
          },
        ],
      };
    }

    // -------- 散点图 --------
    case 'scatter': {
      const xMetric = metrics[0] || columns[0];
      const yMetric = metrics[1] || metrics[0] || columns[columns.length - 1];
      return {
        ...base,
        xAxis: { type: 'value', name: xMetric },
        yAxis: { type: 'value', name: yMetric },
        series: [
          {
            type: 'scatter',
            data: rows.map((r) => [Number(r[xMetric]) || 0, Number(r[yMetric]) || 0]),
            symbolSize: 8,
          },
        ],
      };
    }

    // -------- 雷达图 --------
    case 'radar': {
      const indicatorCols = metrics.length > 0 ? metrics : dims.slice(0, 6);
      const maxVal = Math.max(
        ...indicatorCols.flatMap((col) => rows.map((r) => Number(r[col]) || 0)),
        1,
      );
      return {
        ...base,
        radar: {
          indicator: indicatorCols.map((col) => ({
            name: col,
            max: Math.ceil(maxVal * 1.3),
          })),
        },
        series: [
          {
            type: 'radar',
            data: [
              {
                name: style.title?.text || '数据',
                value: indicatorCols.map(
                  (col) =>
                    rows.reduce((sum, r) => sum + (Number(r[col]) || 0), 0) /
                    (rows.length || 1),
                ),
              },
            ],
          },
        ],
      };
    }

    // -------- 漏斗图 --------
    case 'funnel': {
      const fData = rows.map((r) => ({
        name: String(r[xCol] ?? ''),
        value: Number(r[yCol]) || 0,
      }));
      return {
        ...base,
        series: [
          {
            type: 'funnel',
            left: '10%',
            width: '80%',
            data: fData,
            sort: 'descending',
            gap: 2,
            label: { show: true, position: 'inside' },
          },
        ],
      };
    }

    // -------- 仪表盘 --------
    case 'gauge': {
      const val = rows.length > 0 ? Number(rows[0][yCol]) : 0;
      return {
        ...base,
        series: [
          {
            type: 'gauge',
            data: [{ value: val || 0, name: yCol }],
            detail: { formatter: '{value}' },
            axisLine: { lineStyle: { width: 18 } },
          },
        ],
      };
    }

    // -------- 矩形树图 --------
    case 'treemap': {
      const tmData = rows.map((r) => ({
        name: String(r[xCol] ?? ''),
        value: Number(r[yCol]) || 0,
      }));
      return {
        ...base,
        series: [
          {
            type: 'treemap',
            data: tmData,
            label: { show: true, formatter: '{b}' },
            roam: false,
          },
        ],
      };
    }

    // -------- 热力图 --------
    case 'heatmap': {
      const yCategoryCol = dims[1] || columns[1] || yCol;
      const xCats = [...new Set(rows.map((r) => String(r[xCol] ?? '')))];
      const yCats = [...new Set(rows.map((r) => String(r[yCategoryCol] ?? '')))];
      const hmData: [string, string, number][] = rows.map((r) => [
        String(r[xCol] ?? ''),
        String(r[yCategoryCol] ?? ''),
        Number(r[yCol]) || 0,
      ]);
      const hmMax = Math.max(...hmData.map((d) => d[2]), 1);
      return {
        ...base,
        xAxis: { type: 'category', data: xCats },
        yAxis: { type: 'category', data: yCats },
        visualMap: {
          min: 0,
          max: hmMax,
          calculable: true,
          orient: 'horizontal',
          left: 'center',
          bottom: 0,
        },
        series: [
          {
            type: 'heatmap',
            data: hmData,
            label: { show: hmData.length <= 30 },
          },
        ],
      };
    }

    // -------- 不支持的类型（sankey / map / wordcloud 等），fallback 为柱状图 --------
    default: {
      const col = yCol;
      return {
        ...base,
        xAxis: {
          type: 'category',
          data: xData,
          axisLabel: { rotate: xData.length > 8 ? 30 : 0 },
        },
        yAxis: { type: 'value' },
        series: [
          {
            name: col,
            type: 'bar',
            data: rows.map((r) => Number(r[col]) || 0),
            barMaxWidth: 40,
          },
        ],
      };
    }
  }
}

// ==================== 子组件：表格渲染 ====================

const TableRenderer: React.FC<{
  data: ChartRendererProps['data'];
  height: number | string;
}> = React.memo(({ data, height }) => {
  const { columns, rows } = data;

  const cols = useMemo(
    () =>
      columns.map((c) => ({
        title: c,
        dataIndex: c,
        key: c,
        ellipsis: true,
        render: (val: unknown) => {
          if (val === null || val === undefined) {
            return <span style={{ color: '#ccc' }}>-</span>;
          }
          return String(val);
        },
      })),
    [columns],
  );

  const dataSource = useMemo(
    () => rows.map((r, i) => ({ ...r, _chartRendererKey: i })),
    [rows],
  );

  return (
    <Table
      columns={cols}
      dataSource={dataSource}
      rowKey="_chartRendererKey"
      size="small"
      scroll={{
        y: typeof height === 'number' ? height - 55 : 300,
      }}
      pagination={
        rows.length > 50
          ? {
              pageSize: 50,
              showSizeChanger: true,
              showTotal: (t) => `共 ${t} 行`,
            }
          : false
      }
    />
  );
});

// ==================== 子组件：指标卡渲染 ====================

const CardRenderer: React.FC<{
  data: ChartRendererProps['data'];
  styleConfig?: ChartStyleConfig | null;
}> = React.memo(({ data, styleConfig }) => {
  const { columns, rows } = data;

  const firstRow = rows[0];
  const label = styleConfig?.title?.text || columns[0] || 'Value';

  let value: number | string;
  if (firstRow) {
    const keys = Object.keys(firstRow).filter((k) => !k.startsWith('_'));
    const raw = firstRow[keys[0]];
    if (typeof raw === 'number') {
      value = raw;
    } else {
      value = String(raw ?? '-');
    }
  } else {
    value = '-';
  }

  return (
    <Card
      style={{
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Statistic
        title={label}
        value={typeof value === 'number' ? value : value}
        valueStyle={{ fontSize: 36, fontWeight: 700 }}
      />
    </Card>
  );
});

// ==================== 主组件 ====================

const ChartRenderer: React.FC<ChartRendererProps> = ({
  chartType,
  data,
  styleConfig = null,
  height = 400,
  loading = false,
}) => {
  // ---------- 解析样式配置 ----------
  const style = useMemo(() => resolveStyle(styleConfig), [styleConfig]);

  // ---------- ECharts option ----------
  const echartsOption = useMemo<EChartsOption | null>(() => {
    if (!data?.columns?.length || !data?.rows?.length) return null;

    // table / card 不需要构建 ECharts option
    if (chartType === 'table' || chartType === 'card') return null;

    try {
      return buildEChartsOption(chartType, data, style);
    } catch {
      return null;
    }
  }, [chartType, data, style]);

  // ==================== 容器样式 ====================
  const containerHeight = height;

  const placeholderContainerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: containerHeight,
    background: '#fafafa',
    borderRadius: 8,
    border: '1px dashed #d9d9d9',
  };

  // ==================== 加载态 ====================
  if (loading) {
    return (
      <div style={placeholderContainerStyle}>
        <Spin tip="加载中..." />
      </div>
    );
  }

  // ==================== 空数据态 ====================
  const hasData = data?.columns?.length > 0 && data?.rows?.length > 0;
  if (!hasData) {
    return (
      <div style={placeholderContainerStyle}>
        <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  // ==================== 表格 ====================
  if (chartType === 'table') {
    return <TableRenderer data={data} height={containerHeight} />;
  }

  // ==================== 指标卡 ====================
  if (chartType === 'card') {
    return <CardRenderer data={data} styleConfig={styleConfig} />;
  }

  // ==================== ECharts 图表 ====================
  if (!echartsOption) {
    return (
      <div style={placeholderContainerStyle}>
        <Empty
          description="无法构建图表配置"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </div>
    );
  }

  return (
    <ReactEChartsCore
      echarts={echarts}
      option={echartsOption}
      style={{ height: containerHeight, width: '100%' }}
      notMerge
      lazyUpdate
    />
  );
};

export default React.memo(ChartRenderer);
