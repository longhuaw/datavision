/**
 * 图表管理 Hook - 封装图表CRUD + NL2SQL + 数据获取 + 克隆
 */
import { useState, useCallback } from 'react';
import api from '@/services/api';
import type { Chart, ChartData, NLQueryRequest, NLQueryResponse, PaginatedData } from '@/types';

export function useCharts() {
  const [loading, setLoading] = useState(false);
  const [list, setList] = useState<Chart[]>([]);
  const [total, setTotal] = useState(0);

  const fetchList = useCallback(async (page = 1, pageSize = 20, category?: string, datasetId?: string) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (category) params.category = category;
      if (datasetId) params.dataset_id = datasetId;
      const res = await api.get<PaginatedData<Chart>>('/charts/', { params });
      setList(res.data.data.items);
      setTotal(res.data.data.total);
      return res.data.data;
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (data: Record<string, unknown>) => {
    const res = await api.post('/charts/', data);
    return res.data.data;
  }, []);

  const update = useCallback(async (id: string, data: Record<string, unknown>) => {
    const res = await api.put(`/charts/${id}`, data);
    return res.data.data;
  }, []);

  const remove = useCallback(async (id: string) => {
    await api.delete(`/charts/${id}`);
  }, []);

  const getDetail = useCallback(async (id: string) => {
    const res = await api.get(`/charts/${id}`);
    return res.data.data as Chart;
  }, []);

  /** 获取图表渲染数据 */
  const fetchData = useCallback(async (chartId: string, forceRefresh = false): Promise<ChartData> => {
    const res = await api.get(`/charts/${chartId}/data`, { params: { force_refresh: forceRefresh } });
    return res.data.data;
  }, []);

  /** 自然语言转 SQL → 图表 */
  const nlQuery = useCallback(async (req: NLQueryRequest): Promise<NLQueryResponse> => {
    const res = await api.post('/charts/nl-query', req);
    return res.data.data;
  }, []);

  /** 推荐图表类型 */
  const recommendType = useCallback(async (datasetId: string) => {
    const res = await api.post('/charts/recommend-type', { dataset_id: datasetId });
    return res.data.data;
  }, []);

  /** 克隆图表 */
  const clone = useCallback(async (id: string, name?: string) => {
    const res = await api.post(`/charts/${id}/clone`, { name });
    return res.data.data;
  }, []);

  /** 刷新图表数据 */
  const refreshData = useCallback(async (id: string) => {
    const res = await api.post(`/charts/${id}/refresh`);
    return res.data.data;
  }, []);

  return { loading, list, total, fetchList, create, update, remove, getDetail, fetchData, nlQuery, recommendType, clone, refreshData };
}
