/**
 * 数据集管理 Hook - 封装数据集CRUD + 预览 + SQL执行 + 字段管理
 */
import { useState, useCallback } from 'react';
import api from '@/services/api';
import type { Dataset, DatasetPreview, PaginatedData } from '@/types';

export function useDatasets() {
  const [loading, setLoading] = useState(false);
  const [list, setList] = useState<Dataset[]>([]);
  const [total, setTotal] = useState(0);

  const fetchList = useCallback(async (page = 1, pageSize = 20, datasourceId?: string, status?: string) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (datasourceId) params.datasource_id = datasourceId;
      if (status) params.status = status;
      const res = await api.get<PaginatedData<Dataset>>('/datasets/', { params });
      setList(res.data.data.items);
      setTotal(res.data.data.total);
      return res.data.data;
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (data: Record<string, unknown>) => {
    const res = await api.post('/datasets/', data);
    return res.data.data;
  }, []);

  const update = useCallback(async (id: string, data: Record<string, unknown>) => {
    const res = await api.put(`/datasets/${id}`, data);
    return res.data.data;
  }, []);

  const remove = useCallback(async (id: string) => {
    await api.delete(`/datasets/${id}`);
  }, []);

  const getDetail = useCallback(async (id: string) => {
    const res = await api.get(`/datasets/${id}`);
    return res.data.data as Dataset;
  }, []);

  const preview = useCallback(async (id: string, limit = 100): Promise<DatasetPreview> => {
    const res = await api.get(`/datasets/${id}/preview`, { params: { limit } });
    return res.data.data;
  }, []);

  const executeSQL = useCallback(async (id: string, sql?: string, limit = 100) => {
    const res = await api.post(`/datasets/${id}/execute`, { sql, limit });
    return res.data.data;
  }, []);

  const getColumns = useCallback(async (id: string) => {
    const res = await api.get(`/datasets/${id}/columns`);
    return res.data.data;
  }, []);

  const updateColumn = useCallback(async (dsId: string, colId: string, data: Record<string, unknown>) => {
    const res = await api.put(`/datasets/${dsId}/columns/${colId}`, data);
    return res.data.data;
  }, []);

  const importColumns = useCallback(async (id: string) => {
    const res = await api.post(`/datasets/${id}/import-columns`);
    return res.data.data;
  }, []);

  return { loading, list, total, fetchList, create, update, remove, getDetail, preview, executeSQL, getColumns, updateColumn, importColumns };
}
