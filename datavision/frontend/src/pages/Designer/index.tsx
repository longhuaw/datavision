/**
 * DataVision 看板设计器
 *
 * 核心功能：拖拽式看板布局设计
 * - 顶部工具栏：返回 / 标题编辑 / 添加图表 / 保存 / 发布 / 预览 / 主题
 * - 主区域：react-grid-layout 网格画布（12列，行高80px）
 * - 每个组件 = 一个 ECharts 图表渲染
 * - 右键画布空白处 → "添加图表" 上下文菜单
 * - 点击组件 → 右侧抽屉配置面板（数据 / 刷新 / 联动）
 * - 拖拽移动 + 角落调整尺寸
 */

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  useRef,
} from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Button,
  Input,
  Select,
  Dropdown,
  Drawer,
  Space,
  Tooltip,
  message,
  Spin,
  Empty,
  Popconfirm,
  Tag,
  InputNumber,
  Switch,
  Badge,
  List,
  Card,
} from 'antd';
import {
  ArrowLeftOutlined,
  PlusOutlined,
  SaveOutlined,
  SendOutlined,
  EyeOutlined,
  ReloadOutlined,
  DeleteOutlined,
  SettingOutlined,
  HolderOutlined,
  BgColorsOutlined,
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
  AppstoreOutlined,
  LinkOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import {
  Responsive,
  WidthProvider,
} from 'react-grid-layout';
import type { Layout as GridLayout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

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
  Dashboard,
  DashboardComponent,
  Chart,
  ChartData,
  ChartType,
} from '@/types';

// ==================== ECharts 注册 ====================

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

const ResponsiveGridLayout = WidthProvider(Responsive);

// ==================== 常量 ====================

const GRID_COLS = 12;
const ROW_HEIGHT = 80;
const DEFAULT_WIDGET_W = 4;
const DEFAULT_WIDGET_H = 4;

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

const THEME_OPTIONS: { value: string; label: string; icon: React.ReactNode }[] = [
  { value: 'default', label: '默认主题', icon: <BgColorsOutlined /> },
  { value: 'dark', label: '暗色主题', icon: <BgColorsOutlined /> },
  { value: 'tech-blue', label: '蓝色科技', icon: <BgColorsOutlined /> },
  { value: 'business-green', label: '绿色清新', icon: <BgColorsOutlined /> },
  { value: 'midnight', label: '午夜紫', icon: <BgColorsOutlined /> },
];

// ==================== Helper: build ECharts option ====================

function buildEChartsOption(
  chartType: ChartType,
  chartData: ChartData | null,
): echarts.EChartsOption | null {
  if (!chartData || !chartData.data?.columns?.length) return null;

  const { columns, rows } = chartData.data;

  const baseOption: echarts.EChartsOption = {
    tooltip: { show: true },
    animationDuration: 800,
  };

  const dimCol = columns[0];
  const metricCols = columns.length > 1 ? columns.slice(1) : columns;
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
        grid: { left: 50, right: 16, top: 10, bottom: 30 },
        xAxis: { type: 'category', data: dimensions, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
        legend: { bottom: 0, textStyle: { fontSize: 10 } },
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
          radius: ['35%', '65%'],
          label: { fontSize: 10 },
        }],
      };
    }
    case 'scatter': {
      const xCol = metricCols[0];
      const yCol = metricCols[1] || metricCols[0];
      return {
        ...baseOption,
        grid: { left: 50, right: 16, top: 10, bottom: 30 },
        xAxis: { type: 'value', name: xCol },
        yAxis: { type: 'value', name: yCol },
        series: [{
          type: 'scatter',
          data: rows.map((r) => [Number(r[xCol]) || 0, Number(r[yCol]) || 0]),
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
        radar: { indicator, radius: '55%' },
        series: [{
          type: 'radar',
          data: [{
            name: '',
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
        series: [{ type: 'funnel', data: fData, sort: 'descending', gap: 2, label: { fontSize: 10 } }],
      };
    }
    case 'gauge': {
      const val = Number(rows[0]?.[metricCols[0]]) || 0;
      return {
        ...baseOption,
        series: [{ type: 'gauge', data: [{ value: val, name: metricCols[0] || '' }], detail: { fontSize: 14 } }],
      };
    }
    case 'heatmap': {
      const hmData: [number, number, number][] = rows.map((r, i) => [0, i, Number(r[metricCols[0]]) || 0]);
      return {
        ...baseOption,
        xAxis: { type: 'category', data: [metricCols[0] || ''] },
        yAxis: { type: 'category', data: dimensions },
        visualMap: { min: 0, max: Math.max(...hmData.map((d) => d[2]), 1), calculable: true, orient: 'horizontal', left: 'center', bottom: 0 },
        series: [{ type: 'heatmap', data: hmData, label: { show: true, fontSize: 10 } }],
      };
    }
    case 'table': {
      return null;
    }
    default: {
      const s = metricCols.map((col) => ({
        name: col,
        type: 'bar' as const,
        data: rows.map((r) => Number(r[col]) || 0),
      }));
      return {
        ...baseOption,
        grid: { left: 50, right: 16, top: 10, bottom: 30 },
        xAxis: { type: 'category', data: dimensions, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
        legend: { bottom: 0, textStyle: { fontSize: 10 } },
        series: s,
      };
    }
  }
}

// ==================== 组件 ====================

const DesignerPage: React.FC = () => {
  const { id: dashboardId } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // ---------- 看板 ----------
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [title, setTitle] = useState('');
  const [theme, setTheme] = useState('default');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // ---------- 画布组件 ----------
  const [components, setComponents] = useState<DashboardComponent[]>([]);
  const [layouts, setLayouts] = useState<Record<string, GridLayout[]>>({ lg: [] });
  const [chartDataMap, setChartDataMap] = useState<Record<string, ChartData | null>>({});
  const [dataLoadingMap, setDataLoadingMap] = useState<Record<string, boolean>>({});

  // ---------- 添加图表 Drawer ----------
  const [addDrawerOpen, setAddDrawerOpen] = useState(false);
  const [charts, setCharts] = useState<Chart[]>([]);
  const [chartsLoading, setChartsLoading] = useState(false);
  const [chartSearch, setChartSearch] = useState('');

  // ---------- 设置 Drawer ----------
  const [settingsDrawerOpen, setSettingsDrawerOpen] = useState(false);
  const [selectedComp, setSelectedComp] = useState<DashboardComponent | null>(null);

  // ---------- 发布下拉 ----------
  const [publishing, setPublishing] = useState(false);

  // ---------- 右键 ----------
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; visible: boolean }>({
    x: 0,
    y: 0,
    visible: false,
  });

  // ---------- Ref ----------
  const canvasRef = useRef<HTMLDivElement>(null);
  const refreshTimersRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});

  // ==================== 数据获取 ====================

  const fetchDashboard = useCallback(async () => {
    if (!dashboardId) return;
    setLoading(true);
    try {
      const res = await api.get<APIResponse<Dashboard>>(`/dashboards/${dashboardId}`);
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('获取看板详情失败');
        return;
      }
      if (!data) return;

      setDashboard(data);
      setTitle(data.title);
      setTheme(data.theme || 'default');
      setComponents(data.components || []);

      // 同步到 react-grid-layout 的 layout
      const gridLayouts: GridLayout[] = (data.components || []).map((comp) => ({
        i: comp.id,
        x: comp.position.x,
        y: comp.position.y,
        w: comp.position.w,
        h: comp.position.h,
        minW: 2,
        minH: 2,
      }));
      setLayouts({ lg: gridLayouts });

      // 加载每个图表的初始数据
      for (const comp of data.components || []) {
        fetchChartData(comp.id, comp.chart_id);
      }
    } catch {
      message.error('网络异常，请稍后重试');
    } finally {
      setLoading(false);
    }
  }, [dashboardId]);

  const fetchCharts = useCallback(async () => {
    setChartsLoading(true);
    try {
      const res = await api.get<APIResponse<Chart[]>>('/charts');
      const { code, data } = res.data;
      if (code === 0 || code === 200) {
        setCharts(Array.isArray(data) ? data : []);
      }
    } catch {
      message.error('获取图表列表失败');
    } finally {
      setChartsLoading(false);
    }
  }, []);

  const fetchChartData = useCallback(
    async (componentId: string, chartId: string) => {
      setDataLoadingMap((prev) => ({ ...prev, [componentId]: true }));
      try {
        const res = await api.get<APIResponse<ChartData>>(`/charts/${chartId}/data`);
        const { code, data } = res.data;
        if (code === 0 || code === 200) {
          setChartDataMap((prev) => ({ ...prev, [componentId]: data ?? null }));
        }
      } catch {
        // 静默处理
      } finally {
        setDataLoadingMap((prev) => ({ ...prev, [componentId]: false }));
      }
    },
    [],
  );

  useEffect(() => {
    fetchDashboard();
    fetchCharts();
  }, [fetchDashboard, fetchCharts]);

  // 清理定时器
  useEffect(() => {
    return () => {
      Object.values(refreshTimersRef.current).forEach(clearInterval);
    };
  }, []);

  // ==================== 看板操作 ====================

  const handleSave = async () => {
    if (!dashboardId || !dashboard) return;
    setSaving(true);
    try {
      const payload: Partial<Dashboard> = {
        ...dashboard,
        title: title.trim(),
        theme,
        components,
      };

      const res = await api.put<APIResponse<Dashboard>>(`/dashboards/${dashboardId}`, payload);
      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('保存失败');
        return;
      }
      message.success('看板已保存');
      // 更新本地状态，避免覆盖
      setDashboard((prev) =>
        prev ? { ...prev, title: title.trim(), theme } : null,
      );
    } catch {
      message.error('网络异常');
    } finally {
      setSaving(false);
    }
  };

  const handleTogglePublish = async (publish: boolean) => {
    if (!dashboardId || !dashboard) return;
    setPublishing(true);
    try {
      const res = await api.put<APIResponse<Dashboard>>(`/dashboards/${dashboardId}`, {
        ...dashboard,
        is_published: publish,
        title: title.trim(),
        theme,
        components,
      });
      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(publish ? '发布失败' : '取消发布失败');
        return;
      }
      message.success(publish ? '看板已发布' : '已取消发布');
      setDashboard((prev) =>
        prev ? { ...prev, is_published: publish } : null,
      );
    } catch {
      message.error('网络异常');
    } finally {
      setPublishing(false);
    }
  };

  const handlePreview = () => {
    if (!dashboardId) return;
    const url = `/view/${dashboardId}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  // ==================== 组件管理 ====================

  const handleAddComponent = async (chart: Chart) => {
    if (!dashboardId) return;

    // 计算默认位置：找一个空闲位置
    const currentLayouts = layouts.lg || [];
    const maxY = currentLayouts.length > 0
      ? Math.max(...currentLayouts.map((l) => l.y + l.h))
      : 0;

    const position = {
      x: 0,
      y: maxY,
      w: DEFAULT_WIDGET_W,
      h: DEFAULT_WIDGET_H,
    };

    try {
      const res = await api.post<APIResponse<DashboardComponent>>(
        `/dashboards/${dashboardId}/components`,
        {
          chart_id: chart.id,
          chart_name: chart.name,
          chart_type: chart.chart_type,
          position,
          z_index: components.length + 1,
          config: null,
          sort_order: components.length,
        },
      );

      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('添加图表失败');
        return;
      }

      if (data) {
        const newComp: DashboardComponent = {
          ...data,
          chart_name: chart.name,
          chart_type: chart.chart_type,
        };

        setComponents((prev) => [...prev, newComp]);

        // 更新 grid layout
        const newLayout: GridLayout = {
          i: data.id,
          x: position.x,
          y: position.y,
          w: position.w,
          h: position.h,
          minW: 2,
          minH: 2,
        };
        setLayouts((prev) => ({
          ...prev,
          lg: [...(prev.lg || []), newLayout],
        }));

        // 加载图表数据
        fetchChartData(data.id, chart.chart_id);
        message.success(`已添加图表: ${chart.name}`);
      }
    } catch {
      message.error('网络异常');
    }

    setAddDrawerOpen(false);
  };

  const handleRemoveComponent = async (compId: string) => {
    try {
      const res = await api.delete<APIResponse<null>>(
        `/dashboards/${dashboardId}/components/${compId}`,
      );
      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('删除失败');
        return;
      }

      setComponents((prev) => prev.filter((c) => c.id !== compId));
      setChartDataMap((prev) => {
        const next = { ...prev };
        delete next[compId];
        return next;
      });
      setLayouts((prev) => ({
        ...prev,
        lg: (prev.lg || []).filter((l) => l.i !== compId),
      }));

      // 清除定时器
      if (refreshTimersRef.current[compId]) {
        clearInterval(refreshTimersRef.current[compId]);
        delete refreshTimersRef.current[compId];
      }

      // 关闭设置抽屉
      if (selectedComp?.id === compId) {
        setSelectedComp(null);
        setSettingsDrawerOpen(false);
      }

      message.success('组件已移除');
    } catch {
      message.error('网络异常');
    }
  };

  const handleRefreshComponent = (compId: string, chartId: string) => {
    fetchChartData(compId, chartId);
  };

  // ==================== 布局变更 ====================

  const layoutUpdateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingLayoutRef = useRef<GridLayout[]>([]);

  const handleLayoutChange = (currentLayout: GridLayout[]) => {
    setLayouts((prev) => ({ ...prev, lg: currentLayout }));

    // 更新 components 中的位置信息
    const newComponents = components.map((comp) => {
      const layout = currentLayout.find((l) => l.i === comp.id);
      if (layout) {
        return {
          ...comp,
          position: { x: layout.x, y: layout.y, w: layout.w, h: layout.h },
        };
      }
      return comp;
    });
    setComponents(newComponents);

    // 缓存并 debounce 后端同步
    pendingLayoutRef.current = currentLayout;
    if (layoutUpdateTimerRef.current) {
      clearTimeout(layoutUpdateTimerRef.current);
    }
    layoutUpdateTimerRef.current = setTimeout(async () => {
      if (!dashboardId) return;
      const pending = pendingLayoutRef.current;
      for (const layout of pending) {
        try {
          await api.put(`/dashboards/${dashboardId}/components/${layout.i}`, {
            position: { x: layout.x, y: layout.y, w: layout.w, h: layout.h },
          });
        } catch {
          // 静默处理位置更新失败
        }
      }
    }, 600);
  };

  // ==================== 右键菜单 ====================

  const handleCanvasContextMenu = (e: React.MouseEvent) => {
    // 只在空白画布上右键时弹出
    const target = e.target as HTMLElement;
    if (target.closest('.dv-widget') || target.closest('.react-grid-item')) {
      return; // 在组件上右键，不处理
    }
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, visible: true });
  };

  const handleCloseContextMenu = () => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
  };

  // 点击任何地方关闭右键菜单
  useEffect(() => {
    const handler = () => setContextMenu((prev) => ({ ...prev, visible: false }));
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, []);

  // ==================== 设置抽屉 ====================

  const handleWidgetSettings = (comp: DashboardComponent) => {
    setSelectedComp(comp);
    setSettingsDrawerOpen(true);
  };

  const handleUpdateComponentConfig = (compId: string, updates: Partial<DashboardComponent>) => {
    setComponents((prev) =>
      prev.map((c) => (c.id === compId ? { ...c, ...updates } : c)),
    );
  };

  // ==================== 发布下拉菜单 ====================

  const publishMenuItems: MenuProps['items'] = [
    {
      key: 'publish',
      icon: <SendOutlined />,
      label: dashboard?.is_published ? '取消发布' : '发布看板',
      onClick: () => handleTogglePublish(!dashboard?.is_published),
      disabled: publishing,
    },
    {
      key: 'preview',
      icon: <EyeOutlined />,
      label: '预览看板',
      onClick: handlePreview,
    },
  ];

  const themeMenuItems: MenuProps['items'] = THEME_OPTIONS.map((opt) => ({
    key: opt.value,
    icon: opt.icon,
    label: opt.label,
    onClick: () => setTheme(opt.value),
  }));

  // ==================== 过滤后的图表列表 ====================

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

  // ==================== 渲染：单个组件 ====================

  const renderWidget = (comp: DashboardComponent) => {
    const compData = chartDataMap[comp.id];
    const compLoading = dataLoadingMap[comp.id];
    const option = compData ? buildEChartsOption(comp.chart_type as ChartType, compData) : null;

    return (
      <div className="dv-widget" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* 组件头部 */}
        <div
          className="dv-widget-header"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 10px',
            borderBottom: '1px solid #f0f0f0',
            background: '#fafafa',
          }}
        >
          <Space size={6}>
            <span style={{ cursor: 'grab', color: '#999', fontSize: 12 }}>
              <HolderOutlined />
            </span>
            <span style={{ fontWeight: 500, fontSize: 13 }}>
              {CHART_TYPE_ICON[comp.chart_type as ChartType] || <BarChartOutlined />}
            </span>
            <span
              style={{
                fontWeight: 500,
                fontSize: 13,
                maxWidth: 120,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={comp.chart_name}
            >
              {comp.chart_name}
            </span>
          </Space>
          <Space size={2}>
            <Tooltip title="刷新数据">
              <Button
                type="text"
                size="small"
                icon={<ReloadOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleRefreshComponent(comp.id, comp.chart_id);
                }}
              />
            </Tooltip>
            <Tooltip title="设置">
              <Button
                type="text"
                size="small"
                icon={<SettingOutlined />}
                onClick={(e) => {
                  e.stopPropagation();
                  handleWidgetSettings(comp);
                }}
              />
            </Tooltip>
            <Popconfirm
              title="确认移除"
              description="确定要从看板中移除此图表吗？"
              onConfirm={() => handleRemoveComponent(comp.id)}
              okText="移除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Tooltip title="移除">
                <Button
                  type="text"
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={(e) => e.stopPropagation()}
                />
              </Tooltip>
            </Popconfirm>
          </Space>
        </div>

        {/* 组件内容 */}
        <div className="dv-widget-body" style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
          {compLoading ? (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
              }}
            >
              <Spin size="small" />
            </div>
          ) : comp.chart_type === 'table' && compData?.data ? (
            <div style={{ height: '100%', overflow: 'auto', fontSize: 11 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: '#fafafa' }}>
                    {compData.data.columns.map((col) => (
                      <th
                        key={col}
                        style={{
                          padding: '3px 6px',
                          border: '1px solid #f0f0f0',
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
                  {compData.data.rows.slice(0, 50).map((row, i) => (
                    <tr key={i}>
                      {compData.data.columns.map((col) => (
                        <td
                          key={col}
                          style={{
                            padding: '2px 6px',
                            border: '1px solid #f0f0f0',
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
            </div>
          ) : option ? (
            <ReactEChartsCore
              echarts={echarts}
              option={option}
              style={{ width: '100%', height: '100%' }}
              notMerge
              lazyUpdate
              opts={{ renderer: 'canvas' }}
            />
          ) : (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: '#bbb',
              }}
            >
              <Empty description="暂无数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            </div>
          )}
        </div>
      </div>
    );
  };

  // ==================== 渲染 ====================

  if (loading) {
    return (
      <div
        style={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Spin size="large" tip="加载看板..." />
      </div>
    );
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* ========== 顶部工具栏 ========== */}
      <div
        style={{
          padding: '8px 16px',
          background: '#fff',
          borderBottom: '1px solid #f0f0f0',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          flexShrink: 0,
          flexWrap: 'wrap',
          zIndex: 10,
        }}
      >
        {/* 返回按钮 */}
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/dashboards')}
        >
          ← 返回看板列表
        </Button>

        {/* 分隔 */}
        <div style={{ width: 1, height: 24, background: '#f0f0f0' }} />

        {/* 看板标题 */}
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="看板标题"
          style={{ width: 200 }}
          size="small"
          maxLength={100}
        />

        {/* 看板状态 */}
        {dashboard && (
          <Badge
            status={dashboard.is_published ? 'success' : 'default'}
            text={dashboard.is_published ? '已发布' : '未发布'}
          />
        )}

        <div style={{ flex: 1 }} />

        {/* 操作按钮组 */}
        <Space size={4}>
          {/* 添加图表 */}
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddDrawerOpen(true)}
            size="small"
          >
            添加图表
          </Button>

          {/* 保存 */}
          <Button
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSave}
            size="small"
          >
            保存
          </Button>

          {/* 发布下拉 */}
          <Dropdown menu={{ items: publishMenuItems }} trigger={['click']}>
            <Button icon={<SendOutlined />} size="small" loading={publishing}>
              发布
            </Button>
          </Dropdown>

          {/* 预览 */}
          <Button
            icon={<EyeOutlined />}
            onClick={handlePreview}
            size="small"
          >
            预览
          </Button>

          {/* 主题选择器 */}
          <Dropdown menu={{ items: themeMenuItems }} trigger={['click']}>
            <Button icon={<BgColorsOutlined />} size="small">
              主题
            </Button>
          </Dropdown>
        </Space>
      </div>

      {/* ========== 画布区域 ========== */}
      <div
        ref={canvasRef}
        className={`dv-canvas ${theme !== 'default' ? theme : ''}`}
        onContextMenu={handleCanvasContextMenu}
        style={{
          flex: 1,
          overflow: 'auto',
          position: 'relative',
          padding: 16,
        }}
      >
        {/* 无组件时的空状态 */}
        {(!components || components.length === 0) && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '60%',
              color: '#999',
            }}
          >
            <AppstoreOutlined style={{ fontSize: 64, marginBottom: 16, color: '#d9d9d9' }} />
            <p style={{ fontSize: 16, marginBottom: 8 }}>空白看板</p>
            <p style={{ fontSize: 13, marginBottom: 16, color: '#bbb' }}>
              点击左上角「添加图表」或在画布空白处右键添加图表
            </p>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setAddDrawerOpen(true)}
            >
              添加图表
            </Button>
          </div>
        )}

        {/* Grid 布局 */}
        {components.length > 0 && (
          <ResponsiveGridLayout
            className="layout"
            layouts={layouts}
            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
            cols={{ lg: GRID_COLS, md: 10, sm: 8, xs: 6, xxs: 4 }}
            rowHeight={ROW_HEIGHT}
            onLayoutChange={(layout: GridLayout[]) => handleLayoutChange(layout as GridLayout[])}
            draggableHandle=".dv-widget-header"
            isResizable
            isDraggable
            compactType="vertical"
            margin={[12, 12]}
            containerPadding={[0, 0]}
            useCSSTransforms
          >
            {components.map((comp) => (
              <div key={comp.id}>{renderWidget(comp)}</div>
            ))}
          </ResponsiveGridLayout>
        )}
      </div>

      {/* ========== 右键菜单 ========== */}
      {contextMenu.visible && (
        <div
          style={{
            position: 'fixed',
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 1000,
            background: '#fff',
            borderRadius: 6,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            padding: '4px 0',
            minWidth: 160,
          }}
          onClick={handleCloseContextMenu}
        >
          <div
            style={{
              padding: '8px 16px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
              transition: 'background 0.2s',
            }}
            onMouseEnter={(e) => ((e.target as HTMLElement).style.background = '#f5f5f5')}
            onMouseLeave={(e) => ((e.target as HTMLElement).style.background = 'transparent')}
            onClick={() => {
              setAddDrawerOpen(true);
              handleCloseContextMenu();
            }}
          >
            <PlusOutlined style={{ color: '#1677ff' }} />
            <span>添加图表</span>
          </div>
        </div>
      )}

      {/* ========== 添加图表 Drawer ========== */}
      <Drawer
        title="添加图表"
        open={addDrawerOpen}
        onClose={() => setAddDrawerOpen(false)}
        width={420}
        destroyOnClose
      >
        <div style={{ marginBottom: 12 }}>
          <Input
            placeholder="搜索图表..."
            prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
            allowClear
            value={chartSearch}
            onChange={(e) => setChartSearch(e.target.value)}
          />
        </div>

        {chartsLoading ? (
          <div style={{ textAlign: 'center', padding: 60 }}>
            <Spin />
          </div>
        ) : filteredCharts.length === 0 ? (
          <Empty
            description={chartSearch ? '没有匹配的图表' : '暂无图表，请先在图表工作台创建'}
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          >
            <Button type="primary" size="small" onClick={() => navigate('/charts')}>
              前往图表工作台
            </Button>
          </Empty>
        ) : (
          <List
            dataSource={filteredCharts}
            renderItem={(chart) => {
              const alreadyAdded = components.some((c) => c.chart_id === chart.id);
              return (
                <List.Item
                  onClick={() => {
                    if (!alreadyAdded) {
                      handleAddComponent(chart);
                    }
                  }}
                  style={{
                    cursor: alreadyAdded ? 'not-allowed' : 'pointer',
                    opacity: alreadyAdded ? 0.5 : 1,
                    padding: '10px 12px',
                    borderRadius: 6,
                    transition: 'background 0.2s',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      width: '100%',
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
                        fontSize: 16,
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
                        <Tag
                          color="blue"
                          style={{ fontSize: 10, lineHeight: '16px', marginRight: 4 }}
                        >
                          {CHART_TYPE_LABEL[chart.chart_type] || chart.chart_type}
                        </Tag>
                        {chart.dataset_name || '未关联数据集'}
                      </div>
                    </div>
                    {alreadyAdded ? (
                      <Tag color="default" style={{ fontSize: 10 }}>
                        已添加
                      </Tag>
                    ) : (
                      <Button type="primary" size="small" icon={<PlusOutlined />}>
                        添加
                      </Button>
                    )}
                  </div>
                </List.Item>
              );
            }}
          />
        )}
      </Drawer>

      {/* ========== 组件设置 Drawer ========== */}
      <Drawer
        title={
          <Space>
            <SettingOutlined />
            <span>图表设置</span>
            {selectedComp && <Tag color="blue">{selectedComp.chart_name}</Tag>}
          </Space>
        }
        open={settingsDrawerOpen}
        onClose={() => {
          setSettingsDrawerOpen(false);
          setSelectedComp(null);
        }}
        width={400}
        destroyOnClose
      >
        {selectedComp && (
          <div>
            {/* 基本信息 */}
            <Card size="small" title="基本信息" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#999' }}>图表名称</span>
                  <span style={{ fontWeight: 500 }}>{selectedComp.chart_name}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#999' }}>图表类型</span>
                  <Tag>
                    {CHART_TYPE_LABEL[selectedComp.chart_type as ChartType] || selectedComp.chart_type}
                  </Tag>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#999' }}>位置 (x/y)</span>
                  <span>
                    {selectedComp.position.x} × {selectedComp.position.y}
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: '#999' }}>尺寸 (w/h)</span>
                  <span>
                    {selectedComp.position.w} × {selectedComp.position.h}
                  </span>
                </div>
              </div>
            </Card>

            {/* 数据刷新设置 */}
            <Card
              size="small"
              title={
                <span>
                  <ClockCircleOutlined /> 刷新设置
                </span>
              }
              style={{ marginBottom: 16 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 13 }}>自动刷新</span>
                  <Switch
                    size="small"
                    checked={!!selectedComp.config?.autoRefresh}
                    onChange={(checked) => {
                      const newConfig = {
                        ...selectedComp.config,
                        autoRefresh: checked,
                        refreshInterval: checked ? (selectedComp.config?.refreshInterval || 30) : 0,
                      };
                      handleUpdateComponentConfig(selectedComp.id, { config: newConfig });

                      // 管理定时器
                      if (checked) {
                        const interval =
                          (selectedComp.config?.refreshInterval || 30) * 1000;
                        if (refreshTimersRef.current[selectedComp.id]) {
                          clearInterval(refreshTimersRef.current[selectedComp.id]);
                        }
                        refreshTimersRef.current[selectedComp.id] = setInterval(() => {
                          fetchChartData(selectedComp.id, selectedComp.chart_id);
                        }, interval);
                      } else {
                        if (refreshTimersRef.current[selectedComp.id]) {
                          clearInterval(refreshTimersRef.current[selectedComp.id]);
                          delete refreshTimersRef.current[selectedComp.id];
                        }
                      }
                    }}
                  />
                </div>

                {selectedComp.config?.autoRefresh && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 13, whiteSpace: 'nowrap' }}>间隔(秒)</span>
                    <InputNumber
                      size="small"
                      min={5}
                      max={3600}
                      step={5}
                      value={selectedComp.config?.refreshInterval || 30}
                      onChange={(val) => {
                        const newInterval = val ?? 30;
                        const newConfig = {
                          ...selectedComp.config,
                          refreshInterval: newInterval,
                        };
                        handleUpdateComponentConfig(selectedComp.id, { config: newConfig });

                        // 更新定时器
                        if (refreshTimersRef.current[selectedComp.id]) {
                          clearInterval(refreshTimersRef.current[selectedComp.id]);
                          refreshTimersRef.current[selectedComp.id] = setInterval(() => {
                            fetchChartData(selectedComp.id, selectedComp.chart_id);
                          }, newInterval * 1000);
                        }
                      }}
                      style={{ width: 100 }}
                    />
                    <span style={{ fontSize: 12, color: '#999' }}>秒</span>
                  </div>
                )}
              </div>
            </Card>

            {/* 联动设置 */}
            <Card
              size="small"
              title={
                <span>
                  <LinkOutlined /> 联动设置
                </span>
              }
              style={{ marginBottom: 16 }}
            >
              <div style={{ fontSize: 13, color: '#999', marginBottom: 8 }}>
                选择触发字段，当该字段值变化时联动刷新其他图表
              </div>
              <Select
                size="small"
                placeholder="选择触发字段"
                allowClear
                style={{ width: '100%', marginBottom: 8 }}
                value={selectedComp.config?.triggerField || undefined}
                onChange={(val) => {
                  handleUpdateComponentConfig(selectedComp.id, {
                    config: { ...selectedComp.config, triggerField: val || undefined },
                  });
                }}
                options={
                  chartDataMap[selectedComp.id]?.data?.columns.map((col) => ({
                    label: col,
                    value: col,
                  })) || []
                }
              />
              <div style={{ fontSize: 12, color: '#999' }}>
                目标图表：其他组件的图表（联动当前看板中的相关数据）
              </div>
            </Card>

            {/* 操作 */}
            <Popconfirm
              title="确认移除"
              description="确定要从看板中移除此图表吗？"
              onConfirm={() => {
                handleRemoveComponent(selectedComp.id);
                setSettingsDrawerOpen(false);
              }}
              okText="移除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button danger icon={<DeleteOutlined />} block>
                从看板中移除
              </Button>
            </Popconfirm>
          </div>
        )}
      </Drawer>
    </div>
  );
};

export default DesignerPage;
