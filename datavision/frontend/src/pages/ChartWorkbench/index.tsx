/**
 * DataVision 图表工作台
 *
 * 核心功能页：创建 / 编辑图表
 * - 左侧边栏：NL2SQL 自然语言输入 + 图表列表（可搜索）
 * - 主区域：顶部工具栏 + ECharts 图表预览 + 配置面板（数据 / 样式 / 过滤）
 * - NL2SQL 流程：输入 NL → POST /api/v1/charts/nl-query → 展示 SQL + 图表 → 保存
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Layout,
  Input,
  Select,
  Button,
  Tabs,
  Tag,
  message,
  Spin,
  Empty,
  Space,
  Tooltip,
  Radio,
  ColorPicker,
  Switch,
  InputNumber,
  Popconfirm,
  Divider,
  Card,
} from 'antd';
import {
  ThunderboltOutlined,
  SearchOutlined,
  BarChartOutlined,
  LineChartOutlined,
  PieChartOutlined,
  DotChartOutlined,
  HeatMapOutlined,
  FundOutlined,
  RadarChartOutlined,
  NodeIndexOutlined,
  GlobalOutlined,
  TableOutlined,
  DashboardOutlined,
  AreaChartOutlined,
  CloudOutlined,
  PlusOutlined,
  SaveOutlined,
  DeleteOutlined,
  EditOutlined,
  ReloadOutlined,
  CloseCircleOutlined,
  FilterOutlined,
  AppstoreOutlined,
  BgColorsOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import ReactEChartsCore from 'echarts-for-react/lib/core';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import {
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  RadarChart,
  SankeyChart,
  FunnelChart,
  GaugeChart,
  TreemapChart,
  HeatmapChart,
  MapChart,
  CustomChart,
} from 'echarts/charts';
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  MarkLineComponent,
  MarkAreaComponent,
  GraphicComponent,
  VisualMapComponent,
} from 'echarts/components';
import api from '@/services/api';
import type {
  APIResponse,
  Chart,
  ChartType,
  ChartConfig,
  ChartStyleConfig,
  ChartData,
  Dataset,
  DatasetColumn,
  NLQueryRequest,
  NLQueryResponse,
  ChartDimension,
  ChartMetric,
  ChartFilter,
} from '@/types';

// 注册 ECharts 组件
echarts.use([
  CanvasRenderer,
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  RadarChart,
  SankeyChart,
  FunnelChart,
  GaugeChart,
  TreemapChart,
  HeatmapChart,
  MapChart,
  CustomChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  ToolboxComponent,
  MarkLineComponent,
  MarkAreaComponent,
  GraphicComponent,
  VisualMapComponent,
]);

const { Sider, Content } = Layout;

// ==================== 常量 ====================

const CHART_TYPE_ICON: Record<ChartType, React.ReactNode> = {
  line: <LineChartOutlined />,
  bar: <BarChartOutlined />,
  pie: <PieChartOutlined />,
  scatter: <DotChartOutlined />,
  heatmap: <HeatMapOutlined />,
  funnel: <FundOutlined />,
  radar: <RadarChartOutlined />,
  sankey: <NodeIndexOutlined />,
  map: <GlobalOutlined />,
  table: <TableOutlined />,
  gauge: <DashboardOutlined />,
  treemap: <AreaChartOutlined />,
  wordcloud: <CloudOutlined />,
  area: <AreaChartOutlined />,
  card: <DashboardOutlined />,
};

const CHART_TYPE_LABEL: Record<ChartType, string> = {
  line: '折线图',
  bar: '柱状图',
  pie: '饼图',
  scatter: '散点图',
  heatmap: '热力图',
  funnel: '漏斗图',
  radar: '雷达图',
  sankey: '桑基图',
  map: '地图',
  table: '表格',
  gauge: '仪表盘',
  treemap: '矩形树图',
  wordcloud: '词云',
  area: '面积图',
  card: '指标卡',
};

const AGGREGATION_LABEL: Record<string, string> = {
  sum: '求和',
  count: '计数',
  avg: '平均',
  max: '最大',
  min: '最小',
  distinct: '去重计数',
};

const FILTER_OPERATORS: { value: ChartFilter['operator']; label: string }[] = [
  { value: '=', label: '=' },
  { value: '!=', label: '!=' },
  { value: '>', label: '>' },
  { value: '<', label: '<' },
  { value: '>=', label: '>=' },
  { value: '<=', label: '<=' },
  { value: 'IN', label: 'IN' },
  { value: 'LIKE', label: 'LIKE' },
  { value: 'BETWEEN', label: 'BETWEEN' },
  { value: 'IS NULL', label: 'IS NULL' },
  { value: 'IS NOT NULL', label: 'IS NOT NULL' },
];

// ==================== Helper: build ECharts option ====================

function buildEChartsOption(
  chartType: ChartType,
  chartData: ChartData | null,
  style: ChartStyleConfig | null,
): echarts.EChartsOption | null {
  if (!chartData || !chartData.data?.columns?.length) return null;

  const { columns, rows } = chartData.data;
  const st = style || {};

  const baseOption: echarts.EChartsOption = {
    title: {
      text: st.title?.text ?? '',
      show: st.title?.show ?? true,
      textStyle: { fontSize: st.title?.fontSize ?? 16 },
    },
    legend: {
      show: st.legend?.show ?? true,
      bottom: 0,
    },
    tooltip: { show: st.tooltip?.show ?? true },
    animationDuration: st.animation?.enabled === false ? 0 : st.animation?.duration ?? 800,
    color: st.colors ?? undefined,
  };

  // Determine dimension column (first column) and metric columns (rest)
  const dimCol = columns[0];
  const metricCols = columns.slice(1);

  const dimensions = rows.map((r) => String(r[dimCol] ?? ''));

  switch (chartType) {
    case 'bar':
    case 'line':
    case 'area': {
      const series = metricCols.map((col) => ({
        name: col,
        type: chartType === 'area' ? 'line' : chartType,
        data: rows.map((r) => Number(r[col]) || 0),
        areaStyle: chartType === 'area' ? {} : undefined,
        smooth: chartType === 'line' || chartType === 'area',
      }));
      return {
        ...baseOption,
        xAxis: { type: 'category', data: dimensions },
        yAxis: { type: 'value' },
        legend: { ...baseOption.legend, data: metricCols },
        series,
      };
    }

    case 'pie': {
      const pieData = rows.map((r) => ({
        name: String(r[dimCol] ?? ''),
        value: Number(r[metricCols[0]]) || 0,
      }));
      return {
        ...baseOption,
        series: [{
          type: 'pie',
          data: pieData,
          radius: ['40%', '70%'],
          label: { show: true },
          emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } },
        }],
      };
    }

    case 'scatter': {
      const xCol = metricCols[0];
      const yCol = metricCols[1] || metricCols[0];
      return {
        ...baseOption,
        xAxis: { type: 'value', name: xCol },
        yAxis: { type: 'value', name: yCol },
        series: [{
          type: 'scatter',
          data: rows.map((r) => [Number(r[xCol]) || 0, Number(r[yCol]) || 0]),
          symbolSize: 8,
        }],
      };
    }

    case 'radar': {
      const indicator = metricCols.map((col) => {
        const max = Math.max(...rows.map((r) => Number(r[col]) || 0));
        return { name: col, max: max * 1.2 || 1 };
      });
      return {
        ...baseOption,
        radar: { indicator },
        series: [{
          type: 'radar',
          data: [{
            name: '数据',
            value: metricCols.map((col) => {
              const vals = rows.map((r) => Number(r[col]) || 0);
              return vals.reduce((a, b) => a + b, 0) / (vals.length || 1);
            }),
          }],
        }],
      };
    }

    case 'funnel': {
      const fData = rows.map((r) => ({
        name: String(r[dimCol] ?? ''),
        value: Number(r[metricCols[0]]) || 0,
      }));
      return {
        ...baseOption,
        series: [{
          type: 'funnel',
          data: fData,
          sort: 'descending',
          gap: 2,
          label: { show: true, position: 'inside' },
        }],
      };
    }

    case 'gauge': {
      const val = Number(rows[0]?.[metricCols[0]]) || 0;
      return {
        ...baseOption,
        series: [{
          type: 'gauge',
          data: [{ value: val, name: metricCols[0] || '' }],
          axisLine: { lineStyle: { width: 20 } },
          detail: { formatter: '{value}' },
        }],
      };
    }

    case 'heatmap': {
      const hours = rows.map((r) => String(r[dimCol] ?? ''));
      const xCol = metricCols[0] || '';
      const yCol = metricCols[1] || metricCols[0] || '';
      const xCategories = [...new Set(rows.map((r) => String(r[xCol] ?? '')))];
      // Simplified heatmap data
      const hmData: [number, number, number][] = [];
      rows.forEach((r, i) => {
        const xi = xCategories.indexOf(String(r[xCol] ?? ''));
        if (xi >= 0) {
          hmData.push([xi, i, Number(r[yCol]) || 0]);
        }
      });
      return {
        ...baseOption,
        xAxis: { type: 'category', data: xCategories },
        yAxis: { type: 'category', data: hours },
        visualMap: { min: 0, max: Math.max(...hmData.map((d) => d[2]), 1), calculable: true, orient: 'horizontal', left: 'center', bottom: 30 },
        series: [{ type: 'heatmap', data: hmData, label: { show: true } }],
      };
    }

    case 'table': {
      // For table, return null signal — caller renders a Table
      return null;
    }

    default: {
      // Fallback to bar
      const s = metricCols.map((col) => ({
        name: col,
        type: 'bar' as const,
        data: rows.map((r) => Number(r[col]) || 0),
      }));
      return {
        ...baseOption,
        xAxis: { type: 'category', data: dimensions },
        yAxis: { type: 'value' },
        legend: { ...baseOption.legend, data: metricCols },
        series: s,
      };
    }
  }
}

// ==================== 组件 ====================

const ChartWorkbench: React.FC = () => {
  const { id: urlChartId } = useParams<{ id?: string }>();
  const navigate = useNavigate();

  // ---------- 图表列表 ----------
  const [charts, setCharts] = useState<Chart[]>([]);
  const [chartsLoading, setChartsLoading] = useState(false);
  const [chartSearch, setChartSearch] = useState('');

  // ---------- 当前编辑的图表 ----------
  const [currentChart, setCurrentChart] = useState<Chart | null>(null);
  const [chartName, setChartName] = useState('');
  const [chartType, setChartType] = useState<ChartType>('bar');
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | undefined>(undefined);
  const [saving, setSaving] = useState(false);

  // ---------- 数据集 ----------
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  // ---------- 图表数据 ----------
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [dataLoading, setDataLoading] = useState(false);

  // ---------- 配置 ----------
  const [chartConfig, setChartConfig] = useState<ChartConfig>({
    dimensions: [],
    metrics: [],
    filters: [],
    order_by: [],
    limit: 1000,
  });
  const [styleConfig, setStyleConfig] = useState<ChartStyleConfig>({
    title: { text: '', show: true, fontSize: 16 },
    legend: { show: true, position: 'bottom' },
    tooltip: { show: true },
    animation: { enabled: true, duration: 800 },
  });

  // ---------- NL2SQL 状态 ----------
  const [nlPrompt, setNlPrompt] = useState('');
  const [nlLoading, setNlLoading] = useState(false);
  const [nlResult, setNlResult] = useState<NLQueryResponse | null>(null);

  // ---------- 可用字段（从当前选中数据集的 schema_info 中提取） ----------
  const availableFields = useMemo<DatasetColumn[]>(() => {
    const ds = datasets.find((d) => d.id === selectedDatasetId);
    if (!ds?.schema_info) return [];
    return ds.schema_info;
  }, [datasets, selectedDatasetId]);

  const dimensionFields = useMemo(
    () => availableFields.filter((f) => f.is_dimension !== false),
    [availableFields],
  );
  const metricFields = useMemo(
    () => availableFields.filter((f) => f.is_metric !== false),
    [availableFields],
  );

  // 为过滤维度用到的字段
  const filterAvailableFields = useMemo(() => {
    const used = new Set([
      ...chartConfig.dimensions.map((d) => d.field),
      ...chartConfig.metrics.map((m) => m.field),
    ]);
    return availableFields.filter((f) => !used.has(f.column_name));
  }, [availableFields, chartConfig.dimensions, chartConfig.metrics]);

  // ---------- 搜索过滤后的图表列表 ----------
  const filteredCharts = useMemo(() => {
    if (!chartSearch.trim()) return charts;
    const kw = chartSearch.toLowerCase();
    return charts.filter(
      (c) =>
        c.name.toLowerCase().includes(kw) ||
        c.chart_type.toLowerCase().includes(kw) ||
        (c.dataset_name || '').toLowerCase().includes(kw),
    );
  }, [charts, chartSearch]);

  // ==================== 数据获取 ====================

  const fetchCharts = useCallback(async () => {
    setChartsLoading(true);
    try {
      const res = await api.get<APIResponse<Chart[]>>('/charts');
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('获取图表列表失败');
        return;
      }
      setCharts(Array.isArray(data) ? data : []);
    } catch {
      message.error('网络异常，请稍后重试');
    } finally {
      setChartsLoading(false);
    }
  }, []);

  const fetchDatasets = useCallback(async () => {
    try {
      const res = await api.get<APIResponse<Dataset[]>>('/datasets');
      const { code, data } = res.data;
      if (code === 0 || code === 200) {
        setDatasets(Array.isArray(data) ? data : []);
      }
    } catch {
      // 静默
    }
  }, []);

  const fetchChartData = useCallback(async (chartId: string) => {
    setDataLoading(true);
    try {
      const res = await api.get<APIResponse<ChartData>>(`/charts/${chartId}/data`);
      const { code, data } = res.data;
      if (code === 0 || code === 200) {
        setChartData(data ?? null);
      } else {
        message.error('获取图表数据失败');
      }
    } catch {
      message.error('网络异常');
    } finally {
      setDataLoading(false);
    }
  }, []);

  // 根据选中图表 ID 加载图表详情
  const loadChart = useCallback(
    async (chartId: string) => {
      try {
        const res = await api.get<APIResponse<Chart>>(`/charts/${chartId}`);
        const { code, data } = res.data;
        if (code !== 0 && code !== 200) {
          message.error('获取图表详情失败');
          return;
        }
        if (!data) return;

        setCurrentChart(data);
        setChartName(data.name);
        setChartType(data.chart_type);
        setSelectedDatasetId(data.dataset_id);

        if (data.config) {
          setChartConfig({
            dimensions: data.config.dimensions || [],
            metrics: data.config.metrics || [],
            filters: data.config.filters || [],
            order_by: data.config.order_by || [],
            limit: data.config.limit ?? 1000,
          });
        }
        if (data.style_config) {
          setStyleConfig({
            title: { text: data.name, show: true, fontSize: 16, ...data.style_config.title },
            colors: data.style_config.colors,
            legend: { show: true, position: 'bottom', ...data.style_config.legend },
            tooltip: { show: true, ...data.style_config.tooltip },
            animation: { enabled: true, duration: 800, ...data.style_config.animation },
            theme: data.style_config.theme,
          });
        }
        if (data.generated_sql) {
          setNlResult({
            prompt: data.nl_prompt || '',
            generated_sql: data.generated_sql,
            chart_type: data.chart_type,
            confidence: data.nl_confidence ?? 1,
          });
        }

        fetchChartData(chartId);
      } catch {
        message.error('加载图表失败');
      }
    },
    [fetchChartData],
  );

  // 初始加载 & URL 参数变化
  useEffect(() => {
    fetchCharts();
    fetchDatasets();
  }, [fetchCharts, fetchDatasets]);

  useEffect(() => {
    if (urlChartId) {
      loadChart(urlChartId);
    }
  }, [urlChartId, loadChart]);

  // ==================== 图表选择 ====================

  const handleSelectChart = (chart: Chart) => {
    navigate(`/charts/${chart.id}`);
  };

  const handleNewChart = () => {
    setCurrentChart(null);
    setChartName('未命名图表');
    setChartType('bar');
    setSelectedDatasetId(undefined);
    setChartConfig({ dimensions: [], metrics: [], filters: [], order_by: [], limit: 1000 });
    setStyleConfig({
      title: { text: '未命名图表', show: true, fontSize: 16 },
      legend: { show: true, position: 'bottom' },
      tooltip: { show: true },
      animation: { enabled: true, duration: 800 },
    });
    setChartData(null);
    setNlPrompt('');
    setNlResult(null);
    navigate('/charts');
  };

  const handleDeleteChart = async (chartId: string) => {
    try {
      const res = await api.delete<APIResponse<null>>(`/charts/${chartId}`);
      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('删除失败');
        return;
      }
      message.success('图表已删除');
      if (currentChart?.id === chartId) {
        handleNewChart();
      }
      fetchCharts();
    } catch {
      message.error('网络异常');
    }
  };

  // ==================== 保存 ====================

  const handleSave = async () => {
    if (!chartName.trim()) {
      message.warning('请输入图表名称');
      return;
    }
    if (!selectedDatasetId) {
      message.warning('请选择数据集');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: chartName.trim(),
        chart_type: chartType,
        dataset_id: selectedDatasetId,
        config: chartConfig,
        style_config: { ...styleConfig, title: { ...styleConfig.title, text: chartName.trim() } },
        nl_prompt: nlPrompt || null,
        generated_sql: nlResult?.generated_sql || null,
        nl_confidence: nlResult?.confidence ?? null,
      };

      if (currentChart?.id) {
        // 更新
        const res = await api.put<APIResponse<Chart>>(`/charts/${currentChart.id}`, payload);
        const { code } = res.data;
        if (code !== 0 && code !== 200) {
          message.error('更新失败');
          return;
        }
        message.success('图表已更新');
        if (res.data.data) {
          setCurrentChart(res.data.data);
        }
      } else {
        // 创建
        const res = await api.post<APIResponse<Chart>>('/charts', {
          ...payload,
          description: '',
          is_template: false,
          category: null,
        });
        const { code, data } = res.data;
        if (code !== 0 && code !== 200) {
          message.error('创建失败');
          return;
        }
        message.success('图表创建成功！');
        if (data?.id) {
          navigate(`/charts/${data.id}`);
        }
      }
      fetchCharts();
    } catch {
      message.error('网络异常');
    } finally {
      setSaving(false);
    }
  };

  // ==================== NL2SQL ====================

  const handleNLQuery = async () => {
    if (!nlPrompt.trim()) {
      message.warning('请输入自然语言描述');
      return;
    }
    setNlLoading(true);
    setNlResult(null);
    try {
      const payload: NLQueryRequest = {
        prompt: nlPrompt.trim(),
        dataset_id: selectedDatasetId,
        chart_type: chartType,
      };
      const res = await api.post<APIResponse<NLQueryResponse>>('/charts/nl-query', payload);
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('NL2SQL 查询失败');
        return;
      }
      if (data) {
        setNlResult(data);
        if (data.chart_type && CHART_TYPE_LABEL[data.chart_type as ChartType]) {
          setChartType(data.chart_type as ChartType);
        }
        if (data.generated_sql) {
          message.success('SQL 生成成功！可以在下方查看');
        }
      }
    } catch {
      message.error('网络异常');
    } finally {
      setNlLoading(false);
    }
  };

  // ==================== 配置操作 ====================

  const addDimension = (field: DatasetColumn) => {
    if (chartConfig.dimensions.some((d) => d.field === field.column_name)) {
      message.info('该维度已添加');
      return;
    }
    setChartConfig((prev) => ({
      ...prev,
      dimensions: [
        ...prev.dimensions,
        { field: field.column_name, alias: field.alias || field.column_name, order: prev.dimensions.length },
      ],
    }));
  };

  const removeDimension = (field: string) => {
    setChartConfig((prev) => ({
      ...prev,
      dimensions: prev.dimensions.filter((d) => d.field !== field),
    }));
  };

  const addMetric = (field: DatasetColumn) => {
    if (chartConfig.metrics.some((m) => m.field === field.column_name)) {
      message.info('该指标已添加');
      return;
    }
    setChartConfig((prev) => ({
      ...prev,
      metrics: [
        ...prev.metrics,
        {
          field: field.column_name,
          aggregation: field.default_aggregation as ChartMetric['aggregation'] || 'sum',
          alias: field.alias || field.column_name,
          order: prev.metrics.length,
        },
      ],
    }));
  };

  const removeMetric = (field: string) => {
    setChartConfig((prev) => ({
      ...prev,
      metrics: prev.metrics.filter((m) => m.field !== field),
    }));
  };

  const updateMetricAggregation = (field: string, aggregation: ChartMetric['aggregation']) => {
    setChartConfig((prev) => ({
      ...prev,
      metrics: prev.metrics.map((m) =>
        m.field === field ? { ...m, aggregation } : m,
      ),
    }));
  };

  const addFilter = () => {
    const newFilter: ChartFilter = {
      field: '',
      operator: '=',
      value: '',
    };
    setChartConfig((prev) => ({
      ...prev,
      filters: [...prev.filters, newFilter],
    }));
  };

  const updateFilter = (index: number, patch: Partial<ChartFilter>) => {
    setChartConfig((prev) => {
      const updated = [...prev.filters];
      updated[index] = { ...updated[index], ...patch };
      return { ...prev, filters: updated };
    });
  };

  const removeFilter = (index: number) => {
    setChartConfig((prev) => ({
      ...prev,
      filters: prev.filters.filter((_, i) => i !== index),
    }));
  };

  // ==================== ECharts option ====================

  const echartsOption = useMemo(
    () => buildEChartsOption(chartType, chartData, styleConfig),
    [chartType, chartData, styleConfig],
  );

  // ==================== 数据集变更处理 ====================

  const handleDatasetChange = (datasetId: string) => {
    setSelectedDatasetId(datasetId);
    // 清空旧的维度 / 指标 / 过滤，因为字段变了
    setChartConfig((prev) => ({
      ...prev,
      dimensions: [],
      metrics: [],
      filters: [],
    }));
  };

  // ==================== 类型切换按钮组 ====================

  const chartTypeButtons: { type: ChartType; label: string; icon: React.ReactNode }[] = [
    { type: 'bar', label: '柱状图', icon: <BarChartOutlined /> },
    { type: 'line', label: '折线图', icon: <LineChartOutlined /> },
    { type: 'area', label: '面积图', icon: <AreaChartOutlined /> },
    { type: 'pie', label: '饼图', icon: <PieChartOutlined /> },
    { type: 'scatter', label: '散点图', icon: <DotChartOutlined /> },
    { type: 'radar', label: '雷达图', icon: <RadarChartOutlined /> },
    { type: 'funnel', label: '漏斗图', icon: <FundOutlined /> },
    { type: 'gauge', label: '仪表盘', icon: <DashboardOutlined /> },
    { type: 'heatmap', label: '热力图', icon: <HeatMapOutlined /> },
    { type: 'table', label: '表格', icon: <TableOutlined /> },
  ];

  // ==================== 渲染辅助 ====================

  const renderChartPreview = () => {
    if (dataLoading) {
      return (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 400,
          }}
        >
          <Spin size="large" tip="加载图表数据..." />
        </div>
      );
    }

    if (!chartData || !chartData.data?.columns?.length) {
      return (
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 400,
            color: '#999',
          }}
        >
          <Empty
            description={
              selectedDatasetId
                ? '点击"获取数据"加载图表预览'
                : '请先选择数据集并配置维度/指标，然后获取数据'
            }
          />
        </div>
      );
    }

    if (chartType === 'table') {
      return renderTablePreview();
    }

    if (!echartsOption) {
      return (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
          <Empty description="无法渲染当前图表" />
        </div>
      );
    }

    return (
      <ReactEChartsCore
        echarts={echarts}
        option={echartsOption}
        style={{ flex: 1, minHeight: 400 }}
        notMerge
        lazyUpdate
        opts={{ renderer: 'canvas' }}
      />
    );
  };

  const renderTablePreview = () => {
    if (!chartData?.data) return null;
    const { columns, rows } = chartData.data;
    if (!columns.length) return <Empty description="无数据" />;

    return (
      <div style={{ flex: 1, overflow: 'auto', minHeight: 400 }}>
        <table
          style={{
            width: '100%',
            borderCollapse: 'collapse',
            fontSize: 13,
          }}
        >
          <thead>
            <tr style={{ background: '#fafafa' }}>
              {columns.map((col) => (
                <th
                  key={col}
                  style={{
                    padding: '8px 12px',
                    border: '1px solid #f0f0f0',
                    textAlign: 'left',
                    fontWeight: 600,
                    whiteSpace: 'nowrap',
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 100).map((row, i) => (
              <tr key={i}>
                {columns.map((col) => (
                  <td
                    key={col}
                    style={{
                      padding: '6px 12px',
                      border: '1px solid #f0f0f0',
                      maxWidth: 300,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {String(row[col] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > 100 && (
          <div style={{ textAlign: 'center', padding: 12, color: '#999' }}>
            仅显示前 100 行，共 {rows.length} 行
          </div>
        )}
      </div>
    );
  };

  // ==================== 渲染 ====================

  return (
    <Layout style={{ height: 'calc(100vh - 56px)', background: '#f5f5f5' }} hasSider>
      {/* ========== 左侧边栏 ========== */}
      <Sider
        width={380}
        style={{
          background: '#fff',
          borderRight: '1px solid #f0f0f0',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* NL2SQL 输入区 */}
        <div style={{ padding: '16px', borderBottom: '1px solid #f0f0f0' }}>
          <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <ThunderboltOutlined style={{ color: '#faad14', fontSize: 16 }} />
            <span style={{ fontWeight: 600, fontSize: 14 }}>NL2SQL 自然语言生成图表</span>
          </div>
          <Input.TextArea
            value={nlPrompt}
            onChange={(e) => setNlPrompt(e.target.value)}
            placeholder="输入自然语言描述你想要的可视化..."
            rows={3}
            style={{ resize: 'none', marginBottom: 8 }}
            disabled={nlLoading}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Select
              value={selectedDatasetId}
              onChange={(val) => setSelectedDatasetId(val)}
              placeholder="选择数据集（可选）"
              allowClear
              style={{ width: 180 }}
              size="small"
              options={datasets.map((d) => ({ label: d.name, value: d.id }))}
            />
            <Button
              type="primary"
              size="small"
              icon={<ThunderboltOutlined />}
              loading={nlLoading}
              onClick={handleNLQuery}
              disabled={!nlPrompt.trim()}
            >
              {nlLoading ? '生成中...' : '生成'}
            </Button>
          </div>

          {/* NL 结果展示 */}
          {nlResult && (
            <Card
              size="small"
              style={{ marginTop: 8, background: '#f6ffed', border: '1px solid #b7eb8f' }}
              styles={{ body: { padding: '8px 12px' } }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <Tag color="green">
                  {CHART_TYPE_LABEL[nlResult.chart_type as ChartType] || nlResult.chart_type}
                </Tag>
                <Tag color="blue">置信度 {(nlResult.confidence * 100).toFixed(0)}%</Tag>
                <Button
                  type="text"
                  size="small"
                  icon={<CloseCircleOutlined />}
                  onClick={() => setNlResult(null)}
                />
              </div>
              <div
                style={{
                  background: '#1e1e1e',
                  color: '#d4d4d4',
                  padding: '8px 10px',
                  borderRadius: 4,
                  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                  fontSize: 12,
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                  maxHeight: 120,
                  overflow: 'auto',
                }}
              >
                {nlResult.generated_sql}
              </div>
            </Card>
          )}
        </div>

        {/* 图表列表 */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '8px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontWeight: 600, fontSize: 14 }}>图表列表</span>
            <Space size={4}>
              <Button type="text" size="small" icon={<ReloadOutlined />} onClick={fetchCharts} />
              <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleNewChart}>
                新建
              </Button>
            </Space>
          </div>

          <div style={{ padding: '0 16px 8px' }}>
            <Input
              placeholder="搜索图表..."
              prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
              allowClear
              size="small"
              value={chartSearch}
              onChange={(e) => setChartSearch(e.target.value)}
            />
          </div>

          <div style={{ flex: 1, overflow: 'auto', padding: '0 8px' }}>
            {chartsLoading ? (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <Spin />
              </div>
            ) : filteredCharts.length === 0 ? (
              <Empty
                description={chartSearch ? '没有匹配的图表' : '暂无图表'}
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                style={{ padding: 40 }}
              >
                <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleNewChart}>
                  新建图表
                </Button>
              </Empty>
            ) : (
              filteredCharts.map((chart) => (
                <div
                  key={chart.id}
                  onClick={() => handleSelectChart(chart)}
                  style={{
                    padding: '10px 12px',
                    marginBottom: 4,
                    borderRadius: 6,
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    background: currentChart?.id === chart.id ? '#e6f4ff' : 'transparent',
                    border: currentChart?.id === chart.id ? '1px solid #1677ff' : '1px solid transparent',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    if (currentChart?.id !== chart.id) {
                      (e.currentTarget as HTMLElement).style.background = '#fafafa';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (currentChart?.id !== chart.id) {
                      (e.currentTarget as HTMLElement).style.background = 'transparent';
                    }
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 6,
                      background: '#f0f5ff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 18,
                      color: '#1677ff',
                      flexShrink: 0,
                    }}
                  >
                    {CHART_TYPE_ICON[chart.chart_type] || <BarChartOutlined />}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontWeight: 500,
                        fontSize: 13,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {chart.name}
                    </div>
                    <div style={{ fontSize: 11, color: '#999', marginTop: 2 }}>
                      {chart.dataset_name || '未关联数据集'}
                    </div>
                  </div>
                  <Popconfirm
                    title="确认删除"
                    description="确定要删除此图表吗？"
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleDeleteChart(chart.id);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                    okText="删除"
                    cancelText="取消"
                    okButtonProps={{ danger: true }}
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>
                </div>
              ))
            )}
          </div>
        </div>
      </Sider>

      {/* ========== 主区域 ========== */}
      <Content style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {/* 顶部工具栏 */}
        <div
          style={{
            padding: '10px 16px',
            background: '#fff',
            borderBottom: '1px solid #f0f0f0',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <Input
            value={chartName}
            onChange={(e) => setChartName(e.target.value)}
            placeholder="图表名称"
            style={{ width: 180 }}
            size="small"
            prefix={<EditOutlined style={{ color: '#bfbfbf' }} />}
          />

          <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            {chartTypeButtons.slice(0, 6).map(({ type, label, icon }) => (
              <Tooltip title={label} key={type}>
                <Button
                  type={chartType === type ? 'primary' : 'text'}
                  size="small"
                  icon={icon}
                  onClick={() => setChartType(type)}
                />
              </Tooltip>
            ))}
            <Select
              value={chartType}
              onChange={(val) => setChartType(val)}
              size="small"
              style={{ width: 100 }}
              options={chartTypeButtons.map(({ type, label, icon }) => ({
                label: (
                  <span>
                    {icon} {label}
                  </span>
                ),
                value: type,
              }))}
            />
          </div>

          <Divider type="vertical" />

          <span style={{ fontSize: 12, color: '#999' }}>数据集</span>
          <Select
            value={selectedDatasetId}
            onChange={(val) => handleDatasetChange(val)}
            placeholder="选择数据集"
            allowClear
            style={{ width: 180 }}
            size="small"
            options={datasets.map((d) => ({ label: d.name, value: d.id }))}
          />

          <Divider type="vertical" />

          <Space size={4}>
            <Button
              type="text"
              size="small"
              icon={<PlayCircleOutlined />}
              onClick={() => {
                if (currentChart?.id) {
                  fetchChartData(currentChart.id);
                } else {
                  message.info('请先选择数据集并配置维度/指标，然后保存后再获取数据');
                }
              }}
              loading={dataLoading}
            >
              获取数据
            </Button>
            <Button
              type="primary"
              size="small"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSave}
            >
              保存
            </Button>
          </Space>
        </div>

        {/* 图表预览区域 */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            background: '#fff',
            margin: '12px 12px 0',
            borderRadius: 8,
            overflow: 'hidden',
            minHeight: 300,
          }}
        >
          {renderChartPreview()}
        </div>

        {/* 底部配置面板 */}
        <div
          style={{
            margin: '12px',
            background: '#fff',
            borderRadius: 8,
            flex: '0 0 auto',
            maxHeight: 360,
            overflow: 'auto',
          }}
        >
          <Tabs
            defaultActiveKey="data"
            size="small"
            style={{ padding: '0 16px' }}
            items={[
              // ===== "数据" Tab =====
              {
                key: 'data',
                label: (
                  <span>
                    <AppstoreOutlined /> 数据
                  </span>
                ),
                children: (
                  <div style={{ padding: '8px 0', display: 'flex', gap: 24 }}>
                    {/* 可用字段 */}
                    <div style={{ width: 220, flexShrink: 0 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>
                        可用字段
                      </div>
                      {!selectedDatasetId ? (
                        <div style={{ color: '#999', fontSize: 12 }}>
                          请先选择数据集
                        </div>
                      ) : availableFields.length === 0 ? (
                        <div style={{ color: '#999', fontSize: 12 }}>
                          当前数据集无可用字段
                        </div>
                      ) : (
                        <div style={{ maxHeight: 240, overflow: 'auto' }}>
                          <div style={{ fontWeight: 500, fontSize: 12, color: '#666', marginBottom: 4 }}>
                            维度 ({dimensionFields.length})
                          </div>
                          {dimensionFields.map((f) => (
                            <div
                              key={f.column_name}
                              style={{
                                padding: '4px 8px',
                                marginBottom: 2,
                                borderRadius: 4,
                                cursor: 'pointer',
                                fontSize: 12,
                                background: '#f0f5ff',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                              }}
                              onClick={() => addDimension(f)}
                            >
                              <span>{f.alias || f.column_name}</span>
                              <Tag color="blue" style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}>
                                维度
                              </Tag>
                            </div>
                          ))}
                          <div style={{ fontWeight: 500, fontSize: 12, color: '#666', marginBottom: 4, marginTop: 8 }}>
                            指标 ({metricFields.length})
                          </div>
                          {metricFields.map((f) => (
                            <div
                              key={f.column_name}
                              style={{
                                padding: '4px 8px',
                                marginBottom: 2,
                                borderRadius: 4,
                                cursor: 'pointer',
                                fontSize: 12,
                                background: '#fff7e6',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                              }}
                              onClick={() => addMetric(f)}
                            >
                              <span>{f.alias || f.column_name}</span>
                              <Tag color="orange" style={{ fontSize: 10, lineHeight: '16px', margin: 0 }}>
                                指标
                              </Tag>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* 已选配置 */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* 维度 */}
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>维度</div>
                        {chartConfig.dimensions.length === 0 ? (
                          <div style={{ color: '#999', fontSize: 12 }}>
                            点击左侧字段添加维度
                          </div>
                        ) : (
                          <Space wrap size={[4, 4]}>
                            {chartConfig.dimensions.map((d) => (
                              <Tag
                                key={d.field}
                                closable
                                onClose={() => removeDimension(d.field)}
                                color="blue"
                              >
                                {d.alias || d.field}
                              </Tag>
                            ))}
                          </Space>
                        )}
                      </div>

                      {/* 指标 */}
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>指标</div>
                        {chartConfig.metrics.length === 0 ? (
                          <div style={{ color: '#999', fontSize: 12 }}>
                            点击左侧字段添加指标
                          </div>
                        ) : (
                          <Space direction="vertical" size={4} style={{ width: '100%' }}>
                            {chartConfig.metrics.map((m) => (
                              <div
                                key={m.field}
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 8,
                                  background: '#fff7e6',
                                  padding: '4px 8px',
                                  borderRadius: 4,
                                }}
                              >
                                <Tag color="orange">{m.alias || m.field}</Tag>
                                <Select
                                  value={m.aggregation}
                                  onChange={(val) => updateMetricAggregation(m.field, val)}
                                  size="small"
                                  style={{ width: 100 }}
                                  options={Object.entries(AGGREGATION_LABEL).map(([k, v]) => ({
                                    label: v,
                                    value: k,
                                  }))}
                                />
                                <Button
                                  type="text"
                                  size="small"
                                  danger
                                  icon={<CloseCircleOutlined />}
                                  onClick={() => removeMetric(m.field)}
                                />
                              </div>
                            ))}
                          </Space>
                        )}
                      </div>

                      {/* 排序 */}
                      <div style={{ marginBottom: 12 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>排序</div>
                        <Select
                          mode="multiple"
                          size="small"
                          style={{ width: '100%' }}
                          placeholder="选择排序字段"
                          value={chartConfig.order_by?.map((o) => `${o.field}:${o.direction}`) || []}
                          onChange={(vals: string[]) => {
                            const orderBy = vals.map((v) => {
                              const [field, direction] = v.split(':');
                              return { field, direction: direction as 'asc' | 'desc' };
                            });
                            setChartConfig((prev) => ({ ...prev, order_by: orderBy }));
                          }}
                          options={availableFields.map((f) => [
                            { label: `${f.column_name} ASC`, value: `${f.column_name}:asc` },
                            { label: `${f.column_name} DESC`, value: `${f.column_name}:desc` },
                          ]).flat()}
                        />
                      </div>

                      {/* 限制行数 */}
                      <div style={{ marginBottom: 4 }}>
                        <div style={{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}>数据量限制</div>
                        <InputNumber
                          size="small"
                          min={1}
                          max={100000}
                          value={chartConfig.limit}
                          onChange={(val) =>
                            setChartConfig((prev) => ({ ...prev, limit: val ?? 1000 }))
                          }
                          style={{ width: 160 }}
                          addonAfter="行"
                        />
                      </div>
                    </div>
                  </div>
                ),
              },

              // ===== "样式" Tab =====
              {
                key: 'style',
                label: (
                  <span>
                    <BgColorsOutlined /> 样式
                  </span>
                ),
                children: (
                  <div style={{ padding: '8px 0', maxWidth: 500 }}>
                    {/* 标题 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>标题</div>
                      <Space direction="vertical" size={4}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>显示</span>
                          <Switch
                            size="small"
                            checked={styleConfig.title?.show ?? true}
                            onChange={(v) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                title: { ...prev.title, show: v },
                              }))
                            }
                          />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>文字</span>
                          <Input
                            size="small"
                            value={styleConfig.title?.text ?? ''}
                            onChange={(e) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                title: { ...prev.title, text: e.target.value },
                              }))
                            }
                            style={{ width: 200 }}
                          />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>字号</span>
                          <InputNumber
                            size="small"
                            min={10}
                            max={48}
                            value={styleConfig.title?.fontSize ?? 16}
                            onChange={(v) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                title: { ...prev.title, fontSize: v ?? 16 },
                              }))
                            }
                          />
                        </div>
                      </Space>
                    </div>

                    {/* 颜色 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>配色</div>
                      <Space wrap size={[4, 4]}>
                        {(styleConfig.colors ?? []).map((color, i) => (
                          <ColorPicker
                            key={i}
                            value={color}
                            size="small"
                            onChange={(_, hex) => {
                              const newColors = [...(styleConfig.colors || [])];
                              newColors[i] = hex;
                              setStyleConfig((prev) => ({ ...prev, colors: newColors }));
                            }}
                          />
                        ))}
                        <Button
                          size="small"
                          icon={<PlusOutlined />}
                          onClick={() => {
                            setStyleConfig((prev) => ({
                              ...prev,
                              colors: [...(prev.colors || []), '#1677ff'],
                            }));
                          }}
                        />
                        {styleConfig.colors && styleConfig.colors.length > 0 && (
                          <Button
                            size="small"
                            onClick={() =>
                              setStyleConfig((prev) => ({ ...prev, colors: undefined }))
                            }
                          >
                            重置
                          </Button>
                        )}
                      </Space>
                      {(!styleConfig.colors || styleConfig.colors.length === 0) && (
                        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                          未设置时将使用默认配色
                        </div>
                      )}
                    </div>

                    {/* 图例 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>图例</div>
                      <Space direction="vertical" size={4}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>显示</span>
                          <Switch
                            size="small"
                            checked={styleConfig.legend?.show ?? true}
                            onChange={(v) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                legend: { ...prev.legend, show: v },
                              }))
                            }
                          />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>位置</span>
                          <Radio.Group
                            size="small"
                            value={styleConfig.legend?.position ?? 'bottom'}
                            onChange={(e) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                legend: { ...prev.legend, position: e.target.value },
                              }))
                            }
                          >
                            <Radio.Button value="top">顶部</Radio.Button>
                            <Radio.Button value="bottom">底部</Radio.Button>
                            <Radio.Button value="left">左侧</Radio.Button>
                            <Radio.Button value="right">右侧</Radio.Button>
                          </Radio.Group>
                        </div>
                      </Space>
                    </div>

                    {/* 提示框 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>提示框</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontSize: 12, width: 40 }}>显示</span>
                        <Switch
                          size="small"
                          checked={styleConfig.tooltip?.show ?? true}
                          onChange={(v) =>
                            setStyleConfig((prev) => ({
                              ...prev,
                              tooltip: { ...prev.tooltip, show: v },
                            }))
                          }
                        />
                      </div>
                    </div>

                    {/* 动画 */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>动画</div>
                      <Space direction="vertical" size={4}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>启用</span>
                          <Switch
                            size="small"
                            checked={styleConfig.animation?.enabled ?? true}
                            onChange={(v) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                animation: { ...prev.animation, enabled: v },
                              }))
                            }
                          />
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span style={{ fontSize: 12, width: 40 }}>时长</span>
                          <InputNumber
                            size="small"
                            min={0}
                            max={5000}
                            step={100}
                            value={styleConfig.animation?.duration ?? 800}
                            onChange={(v) =>
                              setStyleConfig((prev) => ({
                                ...prev,
                                animation: { ...prev.animation, duration: v ?? 800 },
                              }))
                            }
                            addonAfter="ms"
                          />
                        </div>
                      </Space>
                    </div>
                  </div>
                ),
              },

              // ===== "过滤" Tab =====
              {
                key: 'filter',
                label: (
                  <span>
                    <FilterOutlined /> 过滤
                  </span>
                ),
                children: (
                  <div style={{ padding: '8px 0' }}>
                    <div style={{ marginBottom: 8 }}>
                      <Button size="small" icon={<PlusOutlined />} onClick={addFilter}>
                        添加过滤条件
                      </Button>
                    </div>

                    {chartConfig.filters.length === 0 ? (
                      <div style={{ color: '#999', fontSize: 12, padding: '12px 0' }}>
                        暂无过滤条件，点击上方按钮添加
                      </div>
                    ) : (
                      <Space direction="vertical" size={8} style={{ width: '100%' }}>
                        {chartConfig.filters.map((filter, i) => (
                          <div
                            key={i}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              padding: '6px 10px',
                              background: '#fafafa',
                              borderRadius: 6,
                              flexWrap: 'wrap',
                            }}
                          >
                            <span style={{ fontSize: 11, color: '#999', width: 20 }}>#{i + 1}</span>
                            <Select
                              size="small"
                              value={filter.field || undefined}
                              onChange={(val) => updateFilter(i, { field: val })}
                              placeholder="字段"
                              style={{ width: 130 }}
                              options={[
                                ...chartConfig.dimensions.map((d) => ({
                                  label: d.alias || d.field,
                                  value: d.field,
                                })),
                                ...chartConfig.metrics.map((m) => ({
                                  label: m.alias || m.field,
                                  value: m.field,
                                })),
                                ...filterAvailableFields.map((f) => ({
                                  label: f.column_name,
                                  value: f.column_name,
                                })),
                              ]}
                            />
                            <Select
                              size="small"
                              value={filter.operator}
                              onChange={(val) => updateFilter(i, { operator: val })}
                              style={{ width: 110 }}
                              options={FILTER_OPERATORS}
                            />
                            {!['IS NULL', 'IS NOT NULL'].includes(filter.operator) && (
                              <Input
                                size="small"
                                value={Array.isArray(filter.value) ? filter.value.join(',') : String(filter.value ?? '')}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  if (filter.operator === 'IN' || filter.operator === 'BETWEEN') {
                                    updateFilter(i, { value: val.split(',').map((s) => s.trim()) });
                                  } else {
                                    updateFilter(i, { value: val });
                                  }
                                }}
                                placeholder="值"
                                style={{ width: 120 }}
                              />
                            )}
                            <Button
                              type="text"
                              size="small"
                              danger
                              icon={<DeleteOutlined />}
                              onClick={() => removeFilter(i)}
                            />
                          </div>
                        ))}
                      </Space>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </div>
      </Content>
    </Layout>
  );
};

export default ChartWorkbench;
