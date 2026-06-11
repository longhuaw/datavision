/**
 * 数据源管理 Hook - 封装数据源CRUD + 连接测试 + 元数据同步
 */
import { useState, useCallback } from 'react';
import api from '@/services/api';
import type { DataSource, DataSourceType, PaginatedData } from '@/types';

export function useDatasources() {
  const [loading, setLoading] = useState(false);
  const [list, setList] = useState<DataSource[]>([]);
  const [total, setTotal] = useState(0);

  const fetchList = useCallback(async (page = 1, pageSize = 20, type?: DataSourceType) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: pageSize };
      if (type) params.type = type;
      const res = await api.get<PaginatedData<DataSource>>('/datasources/', { params });
      setList(res.data.data.items);
      setTotal(res.data.data.total);
      return res.data.data;
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (data: Record<string, unknown>) => {
    const res = await api.post('/datasources/', data);
    return res.data.data;
  }, []);

  const update = useCallback(async (id: string, data: Record<string, unknown>) => {
    const res = await api.put(`/datasources/${id}`, data);
    return res.data.data;
  }, []);

  const remove = useCallback(async (id: string) => {
    await api.delete(`/datasources/${id}`);
  }, []);

  const testConnection = useCallback(async (payload: { type?: string; config?: Record<string, unknown>; ds_id?: string }) => {
    const res = await api.post('/datasources/test', payload);
    return res.data.data;
  }, []);

  const syncMetadata = useCallback(async (id: string) => {
    const res = await api.post(`/datasources/${id}/sync-metadata`);
    return res.data.data;
  }, []);

  const getTables = useCallback(async (id: string) => {
    const res = await api.get(`/datasources/${id}/tables`);
    return res.data.data;
  }, []);

  return { loading, list, total, fetchList, create, update, remove, testConnection, syncMetadata, getTables };
}
