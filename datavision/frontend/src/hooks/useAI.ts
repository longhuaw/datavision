/**
 * AI 助手 Hook - NL2SQL、智能分析、图表推荐、标题生成、问题建议
 */
import { useState, useCallback } from 'react';
import api from '@/services/api';
import type { NLQueryResponse, ChartData, AIAnalysisResult } from '@/types';

export function useAI() {
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false); // NL2SQL 专用 loading

  /** 自然语言转 SQL */
  const nl2sql = useCallback(async (prompt: string, datasetId: string): Promise<NLQueryResponse> => {
    setGenerating(true);
    try {
      const res = await api.post('/ai/nl2sql', { prompt, dataset_id: datasetId });
      return res.data.data;
    } finally {
      setGenerating(false);
    }
  }, []);

  /** 分析数据集 */
  const analyze = useCallback(async (datasetId: string, limit = 500): Promise<AIAnalysisResult> => {
    setLoading(true);
    try {
      const res = await api.post('/ai/analyze', { dataset_id: datasetId, limit });
      return res.data.data;
    } finally {
      setLoading(false);
    }
  }, []);

  /** 推荐图表类型 */
  const recommendChart = useCallback(async (params: { dataset_id?: string; columns_info?: Record<string, unknown>[] }) => {
    setLoading(true);
    try {
      const res = await api.post('/ai/chart-recommend', params);
      return res.data.data;
    } finally {
      setLoading(false);
    }
  }, []);

  /** 自动生成标题 */
  const autoTitle = useCallback(async (chartConfig: Record<string, unknown>) => {
    const res = await api.post('/ai/auto-title', { chart_config: chartConfig });
    return res.data.data?.titles || [];
  }, []);

  /** 建议自然语言问题 */
  const suggestQuestions = useCallback(async (datasetId: string) => {
    const res = await api.post('/ai/suggest-questions', { dataset_id: datasetId });
    return res.data.data?.questions || [];
  }, []);

  /** 异常检测 */
  const detectAnomalies = useCallback(async (values: number[]) => {
    const res = await api.post('/ai/anomaly-detect', { values });
    return res.data.data?.anomalies || [];
  }, []);

  /** NL2SQL 查询历史 */
  const getHistory = useCallback(async (page = 1, pageSize = 20) => {
    const res = await api.get('/ai/nl2sql/history', { params: { page, page_size: pageSize } });
    return res.data.data;
  }, []);

  /** 提交 NL2SQL 反馈 */
  const submitFeedback = useCallback(async (historyId: string, feedback: 'positive' | 'negative' | 'neutral') => {
    await api.post('/ai/nl2sql/feedback', { history_id: historyId, feedback });
  }, []);

  return { loading, generating, nl2sql, analyze, recommendChart, autoTitle, suggestQuestions, detectAnomalies, getHistory, submitFeedback };
}
