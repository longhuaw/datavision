import React, { useState, useCallback, useMemo } from 'react';
import {
  Tabs,
  Select,
  Button,
  Switch,
  Input,
  InputNumber,
  Slider,
  Space,
  Tag,
  Collapse,
} from 'antd';
import {
  PlusOutlined,
  DeleteOutlined,
  HolderOutlined,
} from '@ant-design/icons';
import type {
  ChartConfig,
  ChartStyleConfig,
  ChartDimension,
  ChartMetric,
  ChartFilter,
} from '@/types';

// ==================== Types ====================

interface ChartConfigPanelProps {
  config: ChartConfig;
  styleConfig: ChartStyleConfig;
  onConfigChange: (config: ChartConfig) => void;
  onStyleChange: (style: ChartStyleConfig) => void;
  availableFields: { column_name: string; data_type: string; alias?: string }[];
}

interface SortEntry {
  field: string;
  direction: 'asc' | 'desc';
}

// ==================== Constants ====================

const AGG_OPTIONS = [
  { label: '求和 SUM', value: 'sum' },
  { label: '计数 COUNT', value: 'count' },
  { label: '平均 AVG', value: 'avg' },
  { label: '最大 MAX', value: 'max' },
  { label: '最小 MIN', value: 'min' },
  { label: '去重 DISTINCT', value: 'distinct' },
];

const COLOR_PALETTES: { name: string; colors: string[] }[] = [
  { name: '经典蓝', colors: ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1'] },
  { name: '自然绿', colors: ['#52c41a', '#73d13d', '#95de64', '#b7eb8f', '#389e0d'] },
  { name: '暖橙', colors: ['#fa8c16', '#ffa940', '#ffc069', '#ffd591', '#d46b08'] },
  { name: '冷色调', colors: ['#13c2c2', '#36cfc9', '#5cdbd3', '#87e8de', '#08979c'] },
  { name: '粉紫', colors: ['#eb2f96', '#f759ab', '#ff85c0', '#ffadd2', '#c41d7f'] },
  { name: '深色', colors: ['#2f54eb', '#1d39c4', '#10239e', '#597ef7', '#85a5ff'] },
  { name: '大地', colors: ['#a0d911', '#bae637', '#d3f261', '#eaff8f', '#7cb305'] },
  { name: '霓虹', colors: ['#f5222d', '#fa541c', '#fa8c16', '#faad14', '#fadb14'] },
];

const FILTER_OPERATORS = [
  { label: '=', value: '=' },
  { label: '!=', value: '!=' },
  { label: '>', value: '>' },
  { label: '<', value: '<' },
  { label: '>=', value: '>=' },
  { label: '<=', value: '<=' },
  { label: 'IN', value: 'IN' },
  { label: 'LIKE', value: 'LIKE' },
  { label: 'BETWEEN', value: 'BETWEEN' },
  { label: '为空', value: 'IS NULL' },
  { label: '不为空', value: 'IS NOT NULL' },
];

const PANEL_STYLE: React.CSSProperties = {
  maxHeight: 420,
  overflow: 'auto',
  padding: '0 4px',
};

const SECTION_TITLE: React.CSSProperties = {
  fontWeight: 600,
  fontSize: 13,
  marginBottom: 8,
};

const ROW_STYLE: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 8,
  marginBottom: 6,
};

const LABEL_STYLE: React.CSSProperties = {
  fontSize: 12,
  whiteSpace: 'nowrap',
};

// ==================== Component ====================

const ChartConfigPanel: React.FC<ChartConfigPanelProps> = ({
  config,
  styleConfig,
  onConfigChange,
  onStyleChange,
  availableFields,
}) => {
  const cfg: ChartConfig = config || {
    dimensions: [],
    metrics: [],
    filters: [],
    order_by: [],
    limit: 100,
  };
  const style: ChartStyleConfig = styleConfig || {
    title: { show: true, text: '', fontSize: 16 },
    colors: ['#1890ff', '#52c41a', '#faad14', '#f5222d'],
    legend: { show: true, position: 'bottom' },
    tooltip: { show: true },
    animation: { enabled: true, duration: 1000 },
  };

  const fieldOptions = useMemo(
    () =>
      availableFields.map((f) => ({
        label: f.alias || f.column_name,
        value: f.column_name,
      })),
    [availableFields],
  );

  const [activeTab, setActiveTab] = useState<string>('data');
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  // ==================== Dimensions ====================

  const handleDimensionsChange = useCallback(
    (selectedValues: string[]) => {
      const currentFields = cfg.dimensions.map((d) => d.field);
      const added = selectedValues.filter((v) => !currentFields.includes(v));
      const newDims: ChartDimension[] = [
        ...cfg.dimensions.filter((d) => selectedValues.includes(d.field)),
        ...added.map((v, i) => ({
          field: v,
          alias: v,
          order: cfg.dimensions.length + i,
        })),
      ];
      onConfigChange({ ...cfg, dimensions: newDims });
    },
    [cfg, onConfigChange],
  );

  const removeDimension = useCallback(
    (field: string) => {
      onConfigChange({
        ...cfg,
        dimensions: cfg.dimensions.filter((d) => d.field !== field),
      });
    },
    [cfg, onConfigChange],
  );

  const moveDimension = useCallback(
    (from: number, to: number) => {
      const dims = [...cfg.dimensions];
      const [moved] = dims.splice(from, 1);
      dims.splice(to, 0, moved);
      onConfigChange({
        ...cfg,
        dimensions: dims.map((d, i) => ({ ...d, order: i })),
      });
    },
    [cfg, onConfigChange],
  );

  const handleDimensionDragStart = useCallback(
    (idx: number) => (e: React.DragEvent) => {
      setDragIndex(idx);
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(idx));
    },
    [],
  );

  const handleDimensionDragOver = useCallback(
    (idx: number) => (e: React.DragEvent) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    },
    [],
  );

  const handleDimensionDrop = useCallback(
    (idx: number) => (e: React.DragEvent) => {
      e.preventDefault();
      if (dragIndex !== null && dragIndex !== idx) {
        moveDimension(dragIndex, idx);
      }
      setDragIndex(null);
    },
    [dragIndex, moveDimension],
  );

  // ==================== Metrics ====================

  const addMetric = useCallback(() => {
    const newMetric: ChartMetric = {
      field: availableFields[0]?.column_name || '',
      aggregation: 'sum',
      alias: '',
      order: (cfg.metrics || []).length,
    };
    onConfigChange({ ...cfg, metrics: [...(cfg.metrics || []), newMetric] });
  }, [cfg, onConfigChange, availableFields]);

  const updateMetric = useCallback(
    (idx: number, key: keyof ChartMetric, val: string | number) => {
      const metrics = [...(cfg.metrics || [])];
      metrics[idx] = { ...metrics[idx], [key]: val };
      onConfigChange({ ...cfg, metrics });
    },
    [cfg, onConfigChange],
  );

  const removeMetric = useCallback(
    (idx: number) => {
      onConfigChange({
        ...cfg,
        metrics: (cfg.metrics || []).filter((_, i) => i !== idx),
      });
    },
    [cfg, onConfigChange],
  );

  // ==================== Sort ====================

  const handleSortChange = useCallback(
    (vals: string[]) => {
      const orderBy: SortEntry[] = vals.map((v) => {
        const [field, direction] = v.split(':');
        return { field, direction: direction as 'asc' | 'desc' };
      });
      onConfigChange({ ...cfg, order_by: orderBy });
    },
    [cfg, onConfigChange],
  );

  // ==================== Style helpers ====================

  const applyColorPalette = useCallback(
    (colors: string[]) => {
      onStyleChange({ ...style, colors: [...colors] });
    },
    [style, onStyleChange],
  );

  const toggleColor = useCallback(
    (color: string) => {
      const current = style.colors || [];
      if (current.includes(color)) {
        onStyleChange({ ...style, colors: current.filter((c) => c !== color) });
      } else {
        onStyleChange({ ...style, colors: [...current, color].slice(0, 8) });
      }
    },
    [style, onStyleChange],
  );

  // ==================== Filters ====================

  const addFilter = useCallback(() => {
    const newFilter: ChartFilter = {
      field: availableFields[0]?.column_name || '',
      operator: '=',
      value: '',
    };
    onConfigChange({
      ...cfg,
      filters: [...(cfg.filters || []), newFilter],
    });
  }, [cfg, onConfigChange, availableFields]);

  const updateFilter = useCallback(
    (idx: number, key: keyof ChartFilter, val: string | number | string[]) => {
      const filters = [...(cfg.filters || [])];
      filters[idx] = { ...filters[idx], [key]: val };
      onConfigChange({ ...cfg, filters });
    },
    [cfg, onConfigChange],
  );

  const removeFilter = useCallback(
    (idx: number) => {
      onConfigChange({
        ...cfg,
        filters: (cfg.filters || []).filter((_, i) => i !== idx),
      });
    },
    [cfg, onConfigChange],
  );

  // ==================== Tab items ====================

  const tabItems = useMemo(
    () => [
      // ===== Data Config Tab =====
      {
        key: 'data',
        label: '数据配置',
        children: (
          <div style={PANEL_STYLE}>
            <Collapse
              size="small"
              ghost
              defaultActiveKey={['dimensions', 'metrics', 'sort']}
              items={[
                // Dimensions section
                {
                  key: 'dimensions',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                      维度 (X轴/分组)
                      {cfg.dimensions.length > 0 && (
                        <Tag color="blue" style={{ marginLeft: 8, fontSize: 11 }}>
                          {cfg.dimensions.length}
                        </Tag>
                      )}
                    </span>
                  ),
                  children: (
                    <div>
                      <Select
                        mode="multiple"
                        size="small"
                        style={{ width: '100%' }}
                        placeholder="选择维度字段..."
                        value={cfg.dimensions.map((d) => d.field)}
                        onChange={handleDimensionsChange}
                        options={fieldOptions}
                      />
                      {/* Dimension order – draggable tags */}
                      {cfg.dimensions.length > 0 && (
                        <div style={{ marginTop: 8 }}>
                          <div style={{ fontSize: 11, color: '#999', marginBottom: 4 }}>
                            拖拽调整顺序 (从上到下 = 分组优先级从高到低)
                          </div>
                          {cfg.dimensions.map((d, idx) => (
                            <div
                              key={d.field}
                              draggable
                              onDragStart={handleDimensionDragStart(idx)}
                              onDragOver={handleDimensionDragOver(idx)}
                              onDrop={handleDimensionDrop(idx)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 4,
                                padding: '4px 8px',
                                marginBottom: 4,
                                borderRadius: 4,
                                background: dragIndex === idx ? '#e6f4ff' : '#f0f5ff',
                                border: dragIndex === idx ? '1px dashed #1890ff' : '1px solid #d9e8ff',
                                cursor: 'grab',
                                transition: 'background 0.2s',
                              }}
                            >
                              <HolderOutlined style={{ color: '#bfbfbf', fontSize: 12, cursor: 'grab' }} />
                              <span style={{ flex: 1, fontSize: 12 }}>{d.alias || d.field}</span>
                              <Tag
                                color="blue"
                                closable
                                onClose={(e) => {
                                  e.preventDefault();
                                  removeDimension(d.field);
                                }}
                                style={{ margin: 0, fontSize: 11 }}
                              >
                                维度
                              </Tag>
                            </div>
                          ))}
                        </div>
                      )}
                      <Button
                        size="small"
                        icon={<PlusOutlined />}
                        type="dashed"
                        block
                        style={{ marginTop: 6 }}
                        onClick={() => {
                          const sel = fieldOptions.find(
                            (f) => !cfg.dimensions.some((d) => d.field === f.value),
                          );
                          if (sel) {
                            handleDimensionsChange([
                              ...cfg.dimensions.map((d) => d.field),
                              sel.value,
                            ]);
                          }
                        }}
                      >
                        添加维度
                      </Button>
                    </div>
                  ),
                },
                // Metrics section
                {
                  key: 'metrics',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                      度量 (Y轴/数值)
                      {cfg.metrics.length > 0 && (
                        <Tag color="orange" style={{ marginLeft: 8, fontSize: 11 }}>
                          {cfg.metrics.length}
                        </Tag>
                      )}
                    </span>
                  ),
                  children: (
                    <div>
                      {(cfg.metrics || []).map((m: ChartMetric, i: number) => (
                        <div key={i} style={ROW_STYLE}>
                          <Select
                            size="small"
                            style={{ flex: 2 }}
                            placeholder="选择字段"
                            value={m.field || undefined}
                            onChange={(v) => updateMetric(i, 'field', v)}
                            options={fieldOptions}
                          />
                          <Select
                            size="small"
                            style={{ flex: 2 }}
                            value={m.aggregation}
                            onChange={(v) => updateMetric(i, 'aggregation', v)}
                            options={AGG_OPTIONS}
                          />
                          <Button
                            size="small"
                            danger
                            icon={<DeleteOutlined />}
                            type="text"
                            onClick={() => removeMetric(i)}
                          />
                        </div>
                      ))}
                      <Button
                        size="small"
                        icon={<PlusOutlined />}
                        type="dashed"
                        block
                        onClick={addMetric}
                      >
                        添加度量
                      </Button>
                    </div>
                  ),
                },
                // Sort settings
                {
                  key: 'sort',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                      排序设置
                    </span>
                  ),
                  children: (
                    <div>
                      <Select
                        mode="multiple"
                        size="small"
                        style={{ width: '100%' }}
                        placeholder="选择排序字段..."
                        value={(cfg.order_by || []).map(
                          (o) => `${o.field}:${o.direction}`,
                        )}
                        onChange={handleSortChange}
                        options={fieldOptions.flatMap((f) => [
                          {
                            label: `${f.label} ↑ ASC`,
                            value: `${f.value}:asc`,
                          },
                          {
                            label: `${f.label} ↓ DESC`,
                            value: `${f.value}:desc`,
                          },
                        ])}
                      />
                      <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>
                        按选中顺序应用排序，可配置多个排序条件
                      </div>
                    </div>
                  ),
                },
                // Data limit
                {
                  key: 'limit',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>
                      数据限制
                    </span>
                  ),
                  children: (
                    <div style={{ ...ROW_STYLE, marginBottom: 0 }}>
                      <span style={LABEL_STYLE}>最大返回行数</span>
                      <InputNumber
                        size="small"
                        min={1}
                        max={100000}
                        value={cfg.limit || 100}
                        onChange={(v) =>
                          onConfigChange({ ...cfg, limit: v ?? 100 })
                        }
                        style={{ width: 140 }}
                        addonAfter="行"
                      />
                    </div>
                  ),
                },
              ]}
            />
          </div>
        ),
      },

      // ===== Style Config Tab =====
      {
        key: 'style',
        label: '样式设置',
        children: (
          <div style={PANEL_STYLE}>
            <Collapse
              size="small"
              ghost
              defaultActiveKey={['title', 'color', 'legend', 'tooltip', 'animation']}
              items={[
                // Title section
                {
                  key: 'title',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>标题</span>
                  ),
                  children: (
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <div style={ROW_STYLE}>
                        <span style={{ ...LABEL_STYLE, width: 48 }}>显示</span>
                        <Switch
                          size="small"
                          checked={style.title?.show !== false}
                          onChange={(v) =>
                            onStyleChange({
                              ...style,
                              title: { ...style.title, show: v },
                            })
                          }
                        />
                      </div>
                      {style.title?.show !== false && (
                        <>
                          <div style={ROW_STYLE}>
                            <span style={{ ...LABEL_STYLE, width: 48 }}>文字</span>
                            <Input
                              size="small"
                              placeholder="图表标题"
                              value={style.title?.text || ''}
                              onChange={(e) =>
                                onStyleChange({
                                  ...style,
                                  title: {
                                    ...style.title,
                                    text: e.target.value,
                                  },
                                })
                              }
                              style={{ flex: 1 }}
                            />
                          </div>
                          <div style={ROW_STYLE}>
                            <span style={{ ...LABEL_STYLE, width: 48 }}>字号</span>
                            <InputNumber
                              size="small"
                              min={10}
                              max={48}
                              value={style.title?.fontSize || 16}
                              onChange={(v) =>
                                onStyleChange({
                                  ...style,
                                  title: {
                                    ...style.title,
                                    fontSize: v ?? 16,
                                  },
                                })
                              }
                              addonAfter="px"
                            />
                          </div>
                        </>
                      )}
                    </Space>
                  ),
                },
                // Color palette
                {
                  key: 'color',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>配色方案</span>
                  ),
                  children: (
                    <div>
                      {/* Predefined palettes */}
                      <div style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>
                        预设配色
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                        {COLOR_PALETTES.map((palette) => {
                          const allSelected = palette.colors.every(
                            (c) => style.colors?.includes(c),
                          );
                          return (
                            <div
                              key={palette.name}
                              onClick={() => applyColorPalette(palette.colors)}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '4px 8px',
                                borderRadius: 4,
                                cursor: 'pointer',
                                background: allSelected ? '#e6f4ff' : 'transparent',
                                border: allSelected
                                  ? '1px solid #1890ff'
                                  : '1px solid transparent',
                                transition: 'all 0.2s',
                              }}
                            >
                              <span style={{ fontSize: 11, width: 48, flexShrink: 0 }}>
                                {palette.name}
                              </span>
                              <div style={{ display: 'flex', gap: 3 }}>
                                {palette.colors.map((c) => (
                                  <div
                                    key={c}
                                    style={{
                                      width: 20,
                                      height: 20,
                                      borderRadius: 4,
                                      background: c,
                                      border: '1px solid #d9d9d9',
                                    }}
                                  />
                                ))}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      {/* Custom color picker via swatches */}
                      <div style={{ fontSize: 12, color: '#666', margin: '10px 0 6px' }}>
                        自选颜色 (点击切换)
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {COLOR_PALETTES.flatMap((p) => p.colors)
                          .filter((c, i, arr) => arr.indexOf(c) === i)
                          .map((c) => {
                            const active = (style.colors || []).includes(c);
                            return (
                              <div
                                key={c}
                                onClick={() => toggleColor(c)}
                                style={{
                                  width: 28,
                                  height: 28,
                                  borderRadius: 6,
                                  background: c,
                                  cursor: 'pointer',
                                  border: active
                                    ? '3px solid #000'
                                    : '2px solid #d9d9d9',
                                  boxShadow: active
                                    ? '0 0 0 2px rgba(24,144,255,0.3)'
                                    : 'none',
                                  transition: 'all 0.15s',
                                }}
                                title={c}
                              />
                            );
                          })}
                      </div>
                      {(style.colors || []).length > 0 && (
                        <Button
                          size="small"
                          danger
                          type="link"
                          style={{ padding: 0, marginTop: 8 }}
                          onClick={() =>
                            onStyleChange({ ...style, colors: [] })
                          }
                        >
                          重置为默认
                        </Button>
                      )}
                    </div>
                  ),
                },
                // Legend section
                {
                  key: 'legend',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>图例</span>
                  ),
                  children: (
                    <Space direction="vertical" size={4}>
                      <div style={ROW_STYLE}>
                        <span style={{ ...LABEL_STYLE, width: 48 }}>显示</span>
                        <Switch
                          size="small"
                          checked={style.legend?.show !== false}
                          onChange={(v) =>
                            onStyleChange({
                              ...style,
                              legend: { ...style.legend, show: v },
                            })
                          }
                        />
                      </div>
                      {style.legend?.show !== false && (
                        <div style={ROW_STYLE}>
                          <span style={{ ...LABEL_STYLE, width: 48 }}>位置</span>
                          <Select
                            size="small"
                            style={{ width: 100 }}
                            value={style.legend?.position || 'bottom'}
                            onChange={(v) =>
                              onStyleChange({
                                ...style,
                                legend: { ...style.legend, position: v },
                              })
                            }
                            options={[
                              { label: '上方 top', value: 'top' },
                              { label: '下方 bottom', value: 'bottom' },
                              { label: '左侧 left', value: 'left' },
                              { label: '右侧 right', value: 'right' },
                            ]}
                          />
                        </div>
                      )}
                    </Space>
                  ),
                },
                // Tooltip section
                {
                  key: 'tooltip',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>提示框</span>
                  ),
                  children: (
                    <div style={ROW_STYLE}>
                      <span style={{ ...LABEL_STYLE, width: 48 }}>显示</span>
                      <Switch
                        size="small"
                        checked={style.tooltip?.show !== false}
                        onChange={(v) =>
                          onStyleChange({
                            ...style,
                            tooltip: { show: v },
                          })
                        }
                      />
                    </div>
                  ),
                },
                // Animation section
                {
                  key: 'animation',
                  label: (
                    <span style={{ fontSize: 13, fontWeight: 600 }}>动画</span>
                  ),
                  children: (
                    <Space direction="vertical" size={4} style={{ width: '100%' }}>
                      <div style={ROW_STYLE}>
                        <span style={{ ...LABEL_STYLE, width: 48 }}>启用</span>
                        <Switch
                          size="small"
                          checked={style.animation?.enabled !== false}
                          onChange={(v) =>
                            onStyleChange({
                              ...style,
                              animation: {
                                ...style.animation,
                                enabled: v,
                              },
                            })
                          }
                        />
                      </div>
                      {style.animation?.enabled !== false && (
                        <div>
                          <div style={ROW_STYLE}>
                            <span style={{ ...LABEL_STYLE, width: 48 }}>
                              时长
                            </span>
                            <InputNumber
                              size="small"
                              min={0}
                              max={5000}
                              step={100}
                              value={style.animation?.duration || 1000}
                              onChange={(v) =>
                                onStyleChange({
                                  ...style,
                                  animation: {
                                    ...style.animation,
                                    duration: v ?? 1000,
                                  },
                                })
                              }
                              addonAfter="ms"
                              style={{ width: 120 }}
                            />
                          </div>
                          <Slider
                            min={0}
                            max={3000}
                            step={100}
                            value={style.animation?.duration || 1000}
                            onChange={(v) =>
                              onStyleChange({
                                ...style,
                                animation: {
                                  ...style.animation,
                                  duration: v,
                                },
                              })
                            }
                            style={{ margin: '4px 0' }}
                            styles={{
                              track: { background: '#1890ff' },
                            }}
                          />
                          <div
                            style={{
                              display: 'flex',
                              justifyContent: 'space-between',
                              fontSize: 10,
                              color: '#bfbfbf',
                            }}
                          >
                            <span>0ms</span>
                            <span>3000ms</span>
                          </div>
                        </div>
                      )}
                    </Space>
                  ),
                },
              ]}
            />
          </div>
        ),
      },

      // ===== Filter Tab =====
      {
        key: 'filter',
        label: '过滤条件',
        children: (
          <div style={PANEL_STYLE}>
            <Button
              size="small"
              icon={<PlusOutlined />}
              type="primary"
              ghost
              block
              onClick={addFilter}
              style={{ marginBottom: 10 }}
            >
              添加过滤条件
            </Button>

            {(cfg.filters || []).length === 0 ? (
              <div
                style={{
                  textAlign: 'center',
                  color: '#bfbfbf',
                  fontSize: 12,
                  padding: '20px 0',
                }}
              >
                暂无过滤条件，点击上方按钮添加
              </div>
            ) : (
              <Space direction="vertical" size={8} style={{ width: '100%' }}>
                {(cfg.filters || []).map((f, i) => (
                  <div
                    key={i}
                    style={{
                      padding: '8px 10px',
                      background: '#fafafa',
                      borderRadius: 6,
                      border: '1px solid #f0f0f0',
                    }}
                  >
                    <div
                      style={{
                        ...ROW_STYLE,
                        justifyContent: 'space-between',
                        marginBottom: 4,
                      }}
                    >
                      <span style={{ fontSize: 11, color: '#999' }}>
                        条件 #{i + 1}
                      </span>
                      <Button
                        size="small"
                        danger
                        type="text"
                        icon={<DeleteOutlined />}
                        onClick={() => removeFilter(i)}
                      />
                    </div>
                    <div style={ROW_STYLE}>
                      <Select
                        size="small"
                        style={{ flex: 2 }}
                        placeholder="选择字段"
                        value={f.field || undefined}
                        onChange={(v) => updateFilter(i, 'field', v)}
                        options={fieldOptions}
                      />
                      <Select
                        size="small"
                        style={{ flex: 1 }}
                        value={f.operator}
                        onChange={(v) => updateFilter(i, 'operator', v)}
                        options={FILTER_OPERATORS}
                      />
                    </div>
                    {!['IS NULL', 'IS NOT NULL'].includes(f.operator) && (
                      <div style={{ marginTop: 6 }}>
                        <Input
                          size="small"
                          placeholder={
                            f.operator === 'BETWEEN'
                              ? '值1,值2 (逗号分隔)'
                              : f.operator === 'IN'
                              ? '值1,值2,值3 (逗号分隔)'
                              : '输入值'
                          }
                          value={
                            Array.isArray(f.value)
                              ? f.value.join(',')
                              : String(f.value ?? '')
                          }
                          onChange={(e) => {
                            const raw = e.target.value;
                            if (
                              f.operator === 'IN' ||
                              f.operator === 'BETWEEN'
                            ) {
                              updateFilter(
                                i,
                                'value',
                                raw
                                  .split(',')
                                  .map((s) => s.trim())
                                  .filter(Boolean),
                              );
                            } else {
                              updateFilter(i, 'value', raw);
                            }
                          }}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </Space>
            )}
          </div>
        ),
      },
    ],
    [
      cfg,
      style,
      fieldOptions,
      dragIndex,
      handleDimensionsChange,
      handleDimensionDragStart,
      handleDimensionDragOver,
      handleDimensionDrop,
      removeDimension,
      addMetric,
      updateMetric,
      removeMetric,
      handleSortChange,
      applyColorPalette,
      toggleColor,
      addFilter,
      updateFilter,
      removeFilter,
      onConfigChange,
      onStyleChange,
    ],
  );

  return (
    <Tabs
      size="small"
      activeKey={activeTab}
      onChange={setActiveTab}
      items={tabItems}
    />
  );
};

export default ChartConfigPanel;
