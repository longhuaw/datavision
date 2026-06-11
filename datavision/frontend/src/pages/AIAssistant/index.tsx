/**
 * DataVision AI 智能助手页面
 *
 * 三大功能卡片，2列布局：
 * 1. 智能分析 - 选择数据集 → 摘要统计(Descriptions) + 趋势(方向箭头绿涨红跌) + 异常(红色高亮)
 * 2. 图表推荐 - 推荐卡片含图标 + 理由 + 置信度进度条
 * 3. 自然语言查询 - NL输入 + 对话历史气泡(用户提示词 → SQL + 迷你图表信息)
 *
 * API端点：
 *   POST /api/v1/ai/analyze
 *   POST /api/v1/ai/chart-recommend
 *   POST /api/v1/ai/nl2sql
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card,
  Select,
  Button,
  Descriptions,
  List,
  Tag,
  Spin,
  Typography,
  Divider,
  Input,
  Row,
  Col,
  Space,
  message,
  Empty,
  Progress,
  Tooltip,
} from 'antd';
import {
  RobotOutlined,
  ThunderboltOutlined,
  BulbOutlined,
  LineChartOutlined,
  BarChartOutlined,
  PieChartOutlined,
  DotChartOutlined,
  HeatMapOutlined,
  AreaChartOutlined,
  FundOutlined,
  RadarChartOutlined,
  NodeIndexOutlined,
  GlobalOutlined,
  TableOutlined,
  DashboardOutlined,
  CloudOutlined,
  SendOutlined,
  ClearOutlined,
  SearchOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  MinusOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import api from '@/services/api';
import type { APIResponse, Dataset, NLQueryResponse } from '@/types';

const { Text, Paragraph, Title } = Typography;

// ==================== 常量 ====================

/** 图表类型 → 图标映射 */
const CHART_TYPE_ICON: Record<string, React.ReactNode> = {
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

/** 图表类型 → 中文标签 */
const CHART_TYPE_LABEL: Record<string, string> = {
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

/** 图表类型 → 主题色 */
const CHART_CARD_COLORS: Record<string, string> = {
  line: '#1677ff',
  bar: '#52c41a',
  pie: '#fa8c16',
  scatter: '#722ed1',
  heatmap: '#eb2f96',
  funnel: '#13c2c2',
  radar: '#f5222d',
  sankey: '#2f54eb',
  map: '#1890ff',
  table: '#595959',
  gauge: '#faad14',
  treemap: '#a0d911',
  wordcloud: '#fa541c',
  area: '#1677ff',
  card: '#52c41a',
};

/** NL 查询提示词 */
const NL_QUERY_HINTS = [
  '近30天销售额趋势',
  '各品类销量对比柱状图',
  'Top10热销商品排行',
  '用户增长趋势分析',
  '地区销售分布地图',
];

// ==================== 局部类型 ====================

/** 单字段摘要统计 */
interface ColumnStat {
  count?: number;
  mean?: number;
  min?: number;
  max?: number;
  sum?: number;
  std?: number;
  [key: string]: unknown;
}

/** 趋势项 */
interface TrendItem {
  field: string;
  direction: 'up' | 'down' | 'stable';
  strength: number;
}

/** 异常项 */
interface AnomalyItem {
  field?: string;
  index?: number;
  value?: number;
  deviation_score?: number;
  [key: string]: unknown;
}

/** /ai/analyze 响应体 */
interface AnalyzeResult {
  summary?: Record<string, ColumnStat>;
  trends?: TrendItem[];
  anomalies?: AnomalyItem[];
  insights?: string[];
}

/** /ai/chart-recommend 响应体 */
interface ChartRecommendResult {
  chart_type?: string;
  recommended_type?: string;
  reason?: string;
  explanation?: string;
  confidence?: number;
  fields_used?: string[];
}

/** 对话消息 */
interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  sql?: string;
  chartType?: string;
  confidence?: number;
  time: string;
}

// ==================== 子组件 ====================

/** 趋势方向图标：涨红跌绿(中式惯例) */
const TrendDirection: React.FC<{ direction: string }> = ({ direction }) => {
  if (direction === 'up') return <ArrowUpOutlined style={{ color: '#cf1322', fontWeight: 700 }} />;
  if (direction === 'down') return <ArrowDownOutlined style={{ color: '#389e0d', fontWeight: 700 }} />;
  return <MinusOutlined style={{ color: '#999' }} />;
};

/** SQL 代码块 (深色终端风格) */
const SqlBlock: React.FC<{ sql: string }> = ({ sql }) => (
  <div
    style={{
      background: '#1e1e1e',
      color: '#d4d4d4',
      padding: '12px 16px',
      borderRadius: 8,
      fontFamily: '"Fira Code", "Cascadia Code", Consolas, Monaco, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.7,
      whiteSpace: 'pre-wrap',
      wordBreak: 'break-all',
      overflowX: 'auto',
      maxHeight: 180,
      overflow: 'auto',
      marginTop: 8,
      position: 'relative',
    }}
  >
    {sql}
    <div
      style={{
        position: 'absolute',
        top: 6,
        right: 10,
        fontSize: 10,
        color: '#888',
        fontWeight: 600,
        letterSpacing: 1,
      }}
    >
      SQL
    </div>
  </div>
);

/** 图表推荐卡片 —— 大图标 + 类型名 + 理由 + 置信度进度条 */
const ChartRecommendCard: React.FC<{
  chartType: string;
  reason: string;
  confidence: number;
}> = ({ chartType, reason, confidence }) => {
  const color = CHART_CARD_COLORS[chartType] || '#1677ff';
  const label = CHART_TYPE_LABEL[chartType] || chartType;
  const icon = CHART_TYPE_ICON[chartType] || <LineChartOutlined />;

  return (
    <div
      style={{
        background: `linear-gradient(135deg, ${color}06 0%, ${color}18 100%)`,
        border: `1px solid ${color}33`,
        borderRadius: 14,
        padding: 24,
        textAlign: 'center',
        transition: 'transform 0.2s, box-shadow 0.2s',
        cursor: 'default',
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.transform = 'translateY(-3px)';
        (e.currentTarget as HTMLElement).style.boxShadow = `0 8px 24px ${color}18`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
        (e.currentTarget as HTMLElement).style.boxShadow = 'none';
      }}
    >
      {/* 图标 */}
      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            width: 60,
            height: 60,
            borderRadius: 16,
            background: `linear-gradient(135deg, ${color}22, ${color}44)`,
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 28,
            color,
          }}
        >
          {icon}
        </div>
      </div>

      {/* 图表类型标签 */}
      <div
        style={{
          display: 'inline-block',
          background: `linear-gradient(135deg, ${color}, ${color}cc)`,
          color: '#fff',
          padding: '6px 24px',
          borderRadius: 20,
          fontWeight: 700,
          fontSize: 15,
          marginBottom: 12,
          letterSpacing: 1,
        }}
      >
        {label}
      </div>

      {/* 置信度 */}
      <div style={{ marginBottom: 12 }}>
        <Progress
          percent={Math.round(confidence * 100)}
          size="small"
          strokeColor={{ '0%': color, '100%': `${color}66` }}
          format={(p) => `${p}%`}
          style={{ maxWidth: 200, margin: '0 auto' }}
        />
        <Text type="secondary" style={{ fontSize: 11 }}>
          推荐置信度
        </Text>
      </div>

      {/* 推荐理由 */}
      <Divider style={{ margin: '8px 0' }} />
      <Paragraph
        style={{
          margin: 0,
          fontSize: 13,
          color: '#555',
          lineHeight: 1.7,
        }}
      >
        <InfoCircleOutlined style={{ marginRight: 6, color }} />
        {reason || 'AI 根据数据字段类型、分布特征和字段间关系综合推荐'}
      </Paragraph>
    </div>
  );
};

// ==================== 主组件 ====================

const AIAssistant: React.FC = () => {
  // ---------- 数据集列表 ----------
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDs, setSelectedDs] = useState<string | undefined>();

  // ---------- 加载态 ----------
  const [loading, setLoading] = useState({
    analyze: false,
    recommend: false,
    nl: false,
    datasets: false,
  });

  // ---------- 智能分析 ----------
  const [analyzeResult, setAnalyzeResult] = useState<AnalyzeResult | null>(null);

  // ---------- 图表推荐 ----------
  const [chartRecommend, setChartRecommend] = useState<ChartRecommendResult | null>(null);

  // ---------- 自然语言查询 ----------
  const [nlInput, setNlInput] = useState('');
  const [nlMessages, setNlMessages] = useState<ChatMessage[]>([]);

  // 消息列表底部 ref，用于自动滚动
  const chatEndRef = useRef<HTMLDivElement>(null);

  // ==================== 数据获取 ====================

  const fetchDatasets = useCallback(async () => {
    setLoading((prev) => ({ ...prev, datasets: true }));
    try {
      const res = await api.get<APIResponse<{ items?: Dataset[] }>>('/datasets', {
        params: { page: 1, page_size: 100 },
      });
      const data = res.data;
      if (data.code === 0 || data.code === 200) {
        const items =
          (data.data as { items?: Dataset[] })?.items ||
          (Array.isArray(data.data) ? (data.data as Dataset[]) : []);
        setDatasets(items);
      }
    } catch {
      // 静默处理
    } finally {
      setLoading((prev) => ({ ...prev, datasets: false }));
    }
  }, []);

  useEffect(() => {
    fetchDatasets();
  }, [fetchDatasets]);

  // 自动滚动到底部
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [nlMessages]);

  // ==================== 1. 智能分析 ====================

  const handleAnalyze = async () => {
    if (!selectedDs) {
      message.warning('请先选择要分析的数据集');
      return;
    }
    setLoading((prev) => ({ ...prev, analyze: true }));
    setAnalyzeResult(null);

    try {
      const res = await api.post<APIResponse<AnalyzeResult>>('/ai/analyze', {
        dataset_id: selectedDs,
      });
      const { code, message: msg, data } = res.data;
      if (code === 0 || code === 200) {
        setAnalyzeResult(data || null);
        message.success('智能分析完成');
      } else {
        message.error(msg || '分析失败，请稍后重试');
      }
    } catch {
      message.error('网络异常，分析请求失败');
    } finally {
      setLoading((prev) => ({ ...prev, analyze: false }));
    }
  };

  // ==================== 2. 图表推荐 ====================

  const handleRecommend = async () => {
    if (!selectedDs) {
      message.warning('请先选择要分析的数据集');
      return;
    }
    setLoading((prev) => ({ ...prev, recommend: true }));
    setChartRecommend(null);

    try {
      const res = await api.post<APIResponse<ChartRecommendResult>>('/ai/chart-recommend', {
        dataset_id: selectedDs,
      });
      const { code, message: msg, data } = res.data;
      if (code === 0 || code === 200) {
        setChartRecommend(data || null);
        message.success('图表推荐完成');
      } else {
        message.error(msg || '推荐失败，请稍后重试');
      }
    } catch {
      message.error('网络异常，推荐请求失败');
    } finally {
      setLoading((prev) => ({ ...prev, recommend: false }));
    }
  };

  // ==================== 3. 自然语言查询 ====================

  const handleNLQuery = async () => {
    const prompt = nlInput.trim();
    if (!prompt) {
      message.warning('请输入查询内容');
      return;
    }
    setLoading((prev) => ({ ...prev, nl: true }));

    // 添加用户消息
    const userMsg: ChatMessage = {
      role: 'user',
      content: prompt,
      time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
    };
    setNlMessages((prev) => [...prev, userMsg]);
    setNlInput('');

    try {
      const res = await api.post<APIResponse<NLQueryResponse>>('/ai/nl2sql', {
        prompt,
        dataset_id: selectedDs || undefined,
      });
      const { code, data } = res.data;

      if ((code === 0 || code === 200) && data) {
        const result = data as NLQueryResponse;
        const aiMsg: ChatMessage = {
          role: 'ai',
          content: `已根据"${prompt}"生成 SQL 查询`,
          sql: result.generated_sql,
          chartType: result.chart_type || result.suggested_chart_type,
          confidence: result.confidence,
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        };
        setNlMessages((prev) => [...prev, aiMsg]);
      } else {
        setNlMessages((prev) => [
          ...prev,
          {
            role: 'ai',
            content: '未能生成有效查询，请尝试调整描述方式。',
            time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
          },
        ]);
      }
    } catch {
      setNlMessages((prev) => [
        ...prev,
        {
          role: 'ai',
          content: '请求失败，请检查网络连接后重试。',
          time: new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } finally {
      setLoading((prev) => ({ ...prev, nl: false }));
    }
  };

  /** Enter 发送，Shift+Enter 换行 */
  const handleNLKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleNLQuery();
    }
  };

  // ==================== 渲染：智能分析结果 ====================

  const renderAnalyzeResult = () => {
    if (!analyzeResult) return null;

    const { summary, trends, anomalies, insights } = analyzeResult;
    const hasSummary = summary && Object.keys(summary).length > 0;
    const hasTrends = trends && trends.length > 0;
    const hasAnomalies = anomalies && anomalies.length > 0;
    const hasInsights = insights && insights.length > 0;

    if (!hasSummary && !hasTrends && !hasAnomalies && !hasInsights) {
      return (
        <Empty
          description="暂无分析结果"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ padding: 20 }}
        />
      );
    }

    return (
      <div>
        {/* ===== 摘要统计 (Descriptions) ===== */}
        {hasSummary && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
              <Text strong style={{ fontSize: 14 }}>
                字段摘要统计
              </Text>
              <Tag color="green">{Object.keys(summary!).length} 个字段</Tag>
            </div>
            {Object.entries(summary!).map(([fieldName, stat], idx) => (
              <Descriptions
                key={fieldName}
                bordered
                size="small"
                column={{ xs: 2, sm: 4 }}
                style={{ marginBottom: idx < Object.keys(summary!).length - 1 ? 12 : 0 }}
                title={
                  <Text strong style={{ color: '#1677ff' }}>
                    {fieldName}
                  </Text>
                }
              >
                {stat.count !== undefined && (
                  <Descriptions.Item label="计数">
                    <Text strong style={{ color: '#1a1a1a' }}>
                      {Number(stat.count).toLocaleString()}
                    </Text>
                  </Descriptions.Item>
                )}
                {stat.mean !== undefined && (
                  <Descriptions.Item label="均值">
                    <Text style={{ color: '#52c41a', fontWeight: 500 }}>
                      {Number(stat.mean).toFixed(2)}
                    </Text>
                  </Descriptions.Item>
                )}
                {stat.min !== undefined && (
                  <Descriptions.Item label="最小值">
                    <Text style={{ color: '#fa8c16' }}>{Number(stat.min).toFixed(2)}</Text>
                  </Descriptions.Item>
                )}
                {stat.max !== undefined && (
                  <Descriptions.Item label="最大值">
                    <Text style={{ color: '#722ed1' }}>{Number(stat.max).toFixed(2)}</Text>
                  </Descriptions.Item>
                )}
                {stat.sum !== undefined && (
                  <Descriptions.Item label="总和">
                    <Text style={{ fontWeight: 500 }}>
                      {Number(stat.sum).toLocaleString(undefined, {
                        maximumFractionDigits: 2,
                      })}
                    </Text>
                  </Descriptions.Item>
                )}
                {stat.std !== undefined && (
                  <Descriptions.Item label="标准差">
                    <Text type="secondary">{Number(stat.std).toFixed(4)}</Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            ))}
            <Divider style={{ margin: '16px 0' }} />
          </>
        )}

        {/* ===== 趋势分析 (方向箭头：涨红跌绿) ===== */}
        {hasTrends && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <CheckCircleOutlined style={{ color: '#1677ff', fontSize: 16 }} />
              <Text strong style={{ fontSize: 14 }}>
                趋势分析
              </Text>
              <Tag color="blue">{trends!.length} 个指标</Tag>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginBottom: 8 }}>
              {trends!.map((t, i) => {
                const isUp = t.direction === 'up';
                const isDown = t.direction === 'down';
                const label = isUp ? '上升' : isDown ? '下降' : '稳定';
                const tagColor = isUp ? 'red' : isDown ? 'green' : 'default';
                const bgColor = isUp ? '#fff1f0' : isDown ? '#f6ffed' : '#fafafa';
                const borderColor = isUp ? '#ffccc7' : isDown ? '#b7eb8f' : '#d9d9d9';

                return (
                  <Tag
                    key={i}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 6,
                      fontSize: 13,
                      padding: '6px 16px',
                      borderRadius: 20,
                      border: `1px solid ${borderColor}`,
                      background: bgColor,
                      color: isUp ? '#cf1322' : isDown ? '#389e0d' : '#666',
                      fontWeight: 500,
                    }}
                  >
                    <TrendDirection direction={t.direction} />
                    <b>{t.field}</b>
                    <span>
                      {label} {t.strength}%
                    </span>
                  </Tag>
                );
              })}
            </div>
            <Divider style={{ margin: '16px 0' }} />
          </>
        )}

        {/* ===== 异常检测 (红色高亮) ===== */}
        {hasAnomalies && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <ExclamationCircleOutlined style={{ color: '#f5222d', fontSize: 16 }} />
              <Text strong style={{ color: '#f5222d', fontSize: 14 }}>
                异常检测
              </Text>
              <Tag color="volcano">{anomalies!.length} 个异常点</Tag>
            </div>
            <div
              style={{
                background: '#fff1f0',
                border: '1px solid #ffa39e',
                borderRadius: 10,
                padding: '12px 16px',
              }}
            >
              <List
                size="small"
                dataSource={anomalies}
                split={false}
                renderItem={(item, i) => (
                  <List.Item
                    style={{
                      padding: '8px 0',
                      borderBottom:
                        i < anomalies!.length - 1 ? '1px dashed #ffccc7' : 'none',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        width: '100%',
                        color: '#cf1322',
                      }}
                    >
                      <Tag color="error" style={{ fontWeight: 700 }}>
                        #{i + 1}
                      </Tag>
                      {item.field && (
                        <Text strong style={{ color: '#a8071a' }}>
                          {item.field}
                        </Text>
                      )}
                      {item.value !== undefined && (
                        <Text style={{ color: '#cf1322' }}>
                          值: <b>{item.value}</b>
                        </Text>
                      )}
                      {item.deviation_score !== undefined && (
                        <Tag
                          color="volcano"
                          style={{ fontWeight: 500 }}
                        >
                          偏差 {Number(item.deviation_score).toFixed(3)}
                        </Tag>
                      )}
                    </div>
                  </List.Item>
                )}
              />
            </div>
            <Divider style={{ margin: '16px 0' }} />
          </>
        )}

        {/* ===== 洞察建议 ===== */}
        {hasInsights && (
          <div>
            {insights!.map((s, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 10,
                  marginBottom: 8,
                  padding: '12px 16px',
                  background: 'linear-gradient(135deg, #fffbe6, #fff7e6)',
                  borderRadius: 10,
                  border: '1px solid #ffe58f',
                }}
              >
                <BulbOutlined
                  style={{ color: '#faad14', fontSize: 17, marginTop: 2, flexShrink: 0 }}
                />
                <Text style={{ fontSize: 13, lineHeight: 1.7 }}>{s}</Text>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ==================== 渲染：图表推荐结果 ====================

  const renderChartRecommendResult = () => {
    if (!chartRecommend) return null;

    const chartType =
      chartRecommend.chart_type || chartRecommend.recommended_type || 'bar';
    const reason = chartRecommend.reason || chartRecommend.explanation || '';
    const confidence = chartRecommend.confidence ?? 0.7;
    const fields = chartRecommend.fields_used;

    return (
      <div>
        <ChartRecommendCard
          chartType={chartType}
          reason={reason}
          confidence={confidence}
        />
        {fields && fields.length > 0 && (
          <div style={{ marginTop: 14, textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              参考字段：
            </Text>
            {fields.map((f) => (
              <Tag key={f} color="geekblue" style={{ marginLeft: 4, borderRadius: 10 }}>
                {f}
              </Tag>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ==================== 主渲染 ====================

  return (
    <div
      style={{
        padding: 24,
        maxWidth: 1500,
        margin: '0 auto',
        height: 'calc(100vh - 56px)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* ========== 页面标题栏 ========== */}
      <div
        style={{
          marginBottom: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <Space align="center" size={12}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 12,
              background: 'linear-gradient(135deg, #1677ff, #69b1ff)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 4px 12px rgba(22,119,255,0.3)',
            }}
          >
            <RobotOutlined style={{ fontSize: 22, color: '#fff' }} />
          </div>
          <Title level={4} style={{ margin: 0 }}>
            AI 智能助手
          </Title>
          <Tag color="blue" style={{ borderRadius: 10 }}>
            Beta
          </Tag>
        </Space>

        {/* 全局数据集选择器 */}
        <Select
          placeholder="选择要分析的数据集"
          style={{ width: 300 }}
          value={selectedDs}
          onChange={setSelectedDs}
          allowClear
          showSearch
          loading={loading.datasets}
          optionFilterProp="label"
          options={datasets.map((d) => ({ label: d.name, value: d.id }))}
          notFoundContent={
            loading.datasets ? (
              <Spin size="small" />
            ) : (
              <span style={{ color: '#999' }}>暂无可用数据集</span>
            )
          }
        />
      </div>

      {/* ========== 卡片区域：2列布局 ========== */}
      <Row gutter={[16, 16]} style={{ flex: 1, minHeight: 0 }}>
        {/* ---- 卡1: 智能分析 ---- */}
        <Col xs={24} md={12}>
          <Card
            style={{
              borderRadius: 14,
              overflow: 'hidden',
              border: '1px solid #f0f0f0',
              boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
            }}
            styles={{
              body: {
                padding: analyzeResult ? '16px 20px' : '40px 20px',
                flex: 1,
                overflow: 'auto',
              },
            }}
            title={
              <Space>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, #722ed1, #b37feb)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <BulbOutlined style={{ fontSize: 16, color: '#fff' }} />
                </div>
                <span style={{ fontWeight: 700, fontSize: 15 }}>智能分析</span>
              </Space>
            }
            extra={
              <Button
                type="primary"
                size="small"
                onClick={handleAnalyze}
                loading={loading.analyze}
                disabled={!selectedDs}
                icon={<ThunderboltOutlined />}
                style={{ borderRadius: 8 }}
              >
                {loading.analyze ? '分析中...' : '开始分析'}
              </Button>
            }
          >
            {loading.analyze ? (
              <div style={{ textAlign: 'center', padding: 50 }}>
                <Spin size="large" />
                <div style={{ marginTop: 18, color: '#999', fontSize: 14 }}>
                  正在对数据集执行智能分析...
                </div>
              </div>
            ) : analyzeResult ? (
              renderAnalyzeResult()
            ) : (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <BulbOutlined style={{ fontSize: 52, color: '#e8e8e8' }} />
                <p style={{ color: '#999', marginTop: 16, fontSize: 14 }}>
                  选择数据集，点击"开始分析"获取智能洞察
                </p>
              </div>
            )}
          </Card>
        </Col>

        {/* ---- 卡2: 图表推荐 ---- */}
        <Col xs={24} md={12}>
          <Card
            style={{
              borderRadius: 14,
              overflow: 'hidden',
              border: '1px solid #f0f0f0',
              boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
            }}
            styles={{
              body: {
                padding: chartRecommend ? '16px 20px' : '40px 20px',
                flex: 1,
                overflow: 'auto',
              },
            }}
            title={
              <Space>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, #1677ff, #69b1ff)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <LineChartOutlined style={{ fontSize: 16, color: '#fff' }} />
                </div>
                <span style={{ fontWeight: 700, fontSize: 15 }}>图表推荐</span>
              </Space>
            }
            extra={
              <Button
                type="primary"
                size="small"
                onClick={handleRecommend}
                loading={loading.recommend}
                disabled={!selectedDs}
                icon={<SearchOutlined />}
                style={{ borderRadius: 8 }}
              >
                {loading.recommend ? '推荐中...' : '智能推荐'}
              </Button>
            }
          >
            {loading.recommend ? (
              <div style={{ textAlign: 'center', padding: 50 }}>
                <Spin size="large" />
                <div style={{ marginTop: 18, color: '#999', fontSize: 14 }}>
                  AI 正在分析数据特征，推荐最佳图表...
                </div>
              </div>
            ) : chartRecommend ? (
              renderChartRecommendResult()
            ) : (
              <div style={{ textAlign: 'center', padding: 40 }}>
                <LineChartOutlined style={{ fontSize: 52, color: '#e8e8e8' }} />
                <p style={{ color: '#999', marginTop: 16, fontSize: 14 }}>
                  AI 将根据数据结构自动推荐最佳图表类型
                </p>
              </div>
            )}
          </Card>
        </Col>

        {/* ---- 卡3: 自然语言查询 (全宽) ---- */}
        <Col span={24}>
          <Card
            style={{
              borderRadius: 14,
              overflow: 'hidden',
              border: '1px solid #f0f0f0',
              boxShadow: '0 2px 10px rgba(0,0,0,0.04)',
              display: 'flex',
              flexDirection: 'column',
              height: 520,
            }}
            styles={{
              body: {
                padding: 0,
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              },
            }}
            title={
              <Space>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: 'linear-gradient(135deg, #fa8c16, #ffc069)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <ThunderboltOutlined style={{ fontSize: 16, color: '#fff' }} />
                </div>
                <span style={{ fontWeight: 700, fontSize: 15 }}>自然语言查询</span>
                <Tag color="orange" style={{ borderRadius: 10 }}>
                  NL2SQL
                </Tag>
              </Space>
            }
            extra={
              <Space>
                {nlMessages.length > 0 && (
                  <Tooltip title="清空对话">
                    <Button
                      type="text"
                      size="small"
                      icon={<ClearOutlined />}
                      onClick={() => setNlMessages([])}
                    />
                  </Tooltip>
                )}
              </Space>
            }
          >
            {/* 消息列表 */}
            <div
              style={{
                flex: 1,
                overflow: 'auto',
                padding: '16px 20px',
                background: '#fafbfc',
              }}
            >
              {nlMessages.length === 0 ? (
                /* 空态引导 */
                <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                  <div
                    style={{
                      width: 76,
                      height: 76,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #1677ff14, #1677ff24)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      marginBottom: 20,
                    }}
                  >
                    <ThunderboltOutlined style={{ fontSize: 34, color: '#1677ff' }} />
                  </div>
                  <p style={{ color: '#333', fontSize: 16, fontWeight: 500, marginBottom: 6 }}>
                    用自然语言描述你想要的数据可视化
                  </p>
                  <p style={{ color: '#999', fontSize: 13, marginBottom: 20 }}>
                    例如：近30天销售额趋势、各品类销量对比
                  </p>
                  <div
                    style={{
                      display: 'flex',
                      gap: 8,
                      justifyContent: 'center',
                      flexWrap: 'wrap',
                    }}
                  >
                    {NL_QUERY_HINTS.map((hint) => (
                      <Tag
                        key={hint}
                        style={{
                          cursor: 'pointer',
                          borderRadius: 16,
                          padding: '4px 16px',
                          fontSize: 12,
                          color: '#555',
                          border: '1px solid #e8e8e8',
                          background: '#fff',
                          transition: 'all 0.2s',
                        }}
                        onClick={() => setNlInput(hint)}
                        onMouseEnter={(e) => {
                          (e.currentTarget as HTMLElement).style.borderColor = '#1677ff';
                          (e.currentTarget as HTMLElement).style.color = '#1677ff';
                        }}
                        onMouseLeave={(e) => {
                          (e.currentTarget as HTMLElement).style.borderColor = '#e8e8e8';
                          (e.currentTarget as HTMLElement).style.color = '#555';
                        }}
                      >
                        {hint}
                      </Tag>
                    ))}
                  </div>
                </div>
              ) : (
                /* 消息气泡列表 */
                <>
                  {nlMessages.map((msg, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        marginBottom: 16,
                        flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                        animation: 'fadeSlideIn 0.28s ease',
                      }}
                    >
                      {/* 头像 */}
                      <div
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: '50%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          background:
                            msg.role === 'user'
                              ? 'linear-gradient(135deg, #1677ff, #4096ff)'
                              : 'linear-gradient(135deg, #52c41a, #73d13d)',
                          color: '#fff',
                          fontWeight: 700,
                          fontSize: 13,
                          [msg.role === 'user' ? 'marginLeft' : 'marginRight']: 10,
                        }}
                      >
                        {msg.role === 'user' ? '你' : <RobotOutlined />}
                      </div>

                      {/* 内容气泡 */}
                      <div
                        style={{
                          maxWidth: '78%',
                          padding: '14px 18px',
                          borderRadius:
                            msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                          background:
                            msg.role === 'user'
                              ? 'linear-gradient(135deg, #1677ff, #4096ff)'
                              : '#fff',
                          color: msg.role === 'user' ? '#fff' : '#1a1a1a',
                          boxShadow:
                            msg.role === 'ai'
                              ? '0 1px 6px rgba(0,0,0,0.06)'
                              : '0 3px 12px rgba(22,119,255,0.25)',
                          border: msg.role === 'ai' ? '1px solid #f0f0f0' : 'none',
                        }}
                      >
                        {/* 文字内容 */}
                        <div style={{ fontSize: 14, lineHeight: 1.65 }}>
                          {msg.content}
                        </div>

                        {/* AI 返回：SQL */}
                        {msg.role === 'ai' && msg.sql && <SqlBlock sql={msg.sql} />}

                        {/* AI 返回：图表类型 + 置信度 */}
                        {msg.role === 'ai' && msg.chartType && (
                          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Tag
                              color="blue"
                              style={{
                                borderRadius: 12,
                                padding: '2px 12px',
                                margin: 0,
                              }}
                              icon={CHART_TYPE_ICON[msg.chartType] || <LineChartOutlined />}
                            >
                              {CHART_TYPE_LABEL[msg.chartType] || msg.chartType}
                            </Tag>
                            {msg.confidence !== undefined && (
                              <Tag
                                color="green"
                                style={{ borderRadius: 12, margin: 0 }}
                              >
                                置信度 {Math.round(msg.confidence * 100)}%
                              </Tag>
                            )}
                          </div>
                        )}

                        {/* 时间戳 */}
                        <div
                          style={{
                            fontSize: 10,
                            marginTop: 6,
                            opacity: msg.role === 'user' ? 0.6 : 0.45,
                            textAlign: 'right',
                          }}
                        >
                          {msg.time}
                        </div>
                      </div>
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </>
              )}
            </div>

            {/* 输入区 */}
            <div
              style={{
                padding: '14px 20px',
                borderTop: '1px solid #f0f0f0',
                background: '#fff',
                display: 'flex',
                alignItems: 'flex-end',
                gap: 10,
              }}
            >
              <Input.TextArea
                value={nlInput}
                onChange={(e) => setNlInput(e.target.value)}
                onKeyDown={handleNLKeyDown}
                placeholder="输入自然语言描述你想要的数据可视化... (Enter 发送，Shift+Enter 换行)"
                rows={2}
                disabled={loading.nl}
                style={{
                  resize: 'none',
                  borderRadius: 12,
                  fontSize: 14,
                  border: '1px solid #e0e0e0',
                }}
              />
              <Button
                type="primary"
                icon={loading.nl ? <Spin size="small" /> : <SendOutlined />}
                onClick={handleNLQuery}
                loading={loading.nl}
                disabled={!nlInput.trim() || loading.nl}
                style={{
                  borderRadius: 12,
                  height: 56,
                  minWidth: 56,
                  background: loading.nl
                    ? undefined
                    : 'linear-gradient(135deg, #1677ff, #4096ff)',
                  border: 'none',
                  boxShadow: '0 4px 12px rgba(22,119,255,0.35)',
                }}
              />
            </div>
          </Card>
        </Col>
      </Row>

      {/* 动画 */}
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
};

export default AIAssistant;
