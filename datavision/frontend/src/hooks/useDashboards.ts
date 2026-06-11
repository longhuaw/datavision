/**
 * 看板管理 Hook - 封装看板CRUD + 组件管理 + 发布/分享
 */
import { useState, useCallback } from 'react';
import api from '@/services/api';
import type { Dashboard, PaginatedData } from '@/types';

export function useDashboards() {
  const [loading, setLoading] = useState(false);
  const [list, setList] = useState<Dashboard[]>([]);
  const [total, setTotal] = useState(0);

  const fetchList = useCallback(async (page = 1, pageSize = 20, category?: string, isPublished?: boolean) => {
    setLoading(true);
    try {
      const params: Record<string, string | number | boolean> = { page, page_size: pageSize };
      if (category) params.category = category;
      if (isPublished !== undefined) params.is_published = isPublished;
      const res = await api.get<PaginatedData<Dashboard>>('/dashboards/', { params });
      setList(res.data.data.items);
      setTotal(res.data.data.total);
      return res.data.data;
    } finally {
      setLoading(false);
    }
  }, []);

  const create = useCallback(async (data: Record<string, unknown>) => {
    const res = await api.post('/dashboards/', data);
    return res.data.data;
  }, []);

  const update = useCallback(async (id: string, data: Record<string, unknown>) => {
    const res = await api.put(`/dashboards/${id}`, data);
    return res.data.data;
  }, []);

  const remove = useCallback(async (id: string) => {
    await api.delete(`/dashboards/${id}`);
  }, []);

  const getDetail = useCallback(async (id: string): Promise<Dashboard> => {
    const res = await api.get(`/dashboards/${id}`);
    return res.data.data;
  }, []);

  // ---- 组件管理 ----

  const addComponent = useCallback(async (dashboardId: string, data: Record<string, unknown>) => {
    const res = await api.post(`/dashboards/${dashboardId}/components`, data);
    return res.data.data;
  }, []);

  const updateComponent = useCallback(async (dashboardId: string, compId: string, data: Record<string, unknown>) => {
    const res = await api.put(`/dashboards/${dashboardId}/components/${compId}`, data);
    return res.data.data;
  }, []);

  const removeComponent = useCallback(async (dashboardId: string, compId: string) => {
    await api.delete(`/dashboards/${dashboardId}/components/${compId}`);
  }, []);

  const reorderComponents = useCallback(async (dashboardId: string, compIds: string[]) => {
    const res = await api.put(`/dashboards/${dashboardId}/components/reorder`, compIds);
    return res.data.data;
  }, []);

  /** 获取看板中所有图表的数据 */
  const fetchComponentsData = useCallback(async (dashboardId: string, forceRefresh = false) => {
    const res = await api.get(`/dashboards/${dashboardId}/data`, { params: { force_refresh: forceRefresh } });
    return res.data.data;
  }, []);

  // ---- 发布 ----

  const publish = useCallback(async (dashboardId: string, password?: string, expiresAt?: string) => {
    const res = await api.post(`/dashboards/${dashboardId}/publish`, {
      ...(password ? { password } : {}),
      ...(expiresAt ? { expires_at: expiresAt } : {}),
    });
    return res.data.data;
  }, []);

  const unpublish = useCallback(async (dashboardId: string) => {
    await api.post(`/dashboards/${dashboardId}/unpublish`);
  }, []);

  // ---- 分享 ----

  const getShares = useCallback(async (dashboardId: string) => {
    const res = await api.get(`/dashboards/${dashboardId}/shares`);
    return res.data.data;
  }, []);

  const createShare = useCallback(async (dashboardId: string, data: Record<string, unknown>) => {
    const res = await api.post(`/dashboards/${dashboardId}/shares`, data);
    return res.data.data;
  }, []);

  const deleteShare = useCallback(async (dashboardId: string, shareId: string) => {
    await api.delete(`/dashboards/${dashboardId}/shares/${shareId}`);
  }, []);

  return {
    loading, list, total,
    fetchList, create, update, remove, getDetail,
    addComponent, updateComponent, removeComponent, reorderComponents, fetchComponentsData,
    publish, unpublish,
    getShares, createShare, deleteShare,
  };
}
