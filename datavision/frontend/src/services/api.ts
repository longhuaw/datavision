/**
 * Axios 实例 - 统一封装请求/响应拦截
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { APIResponse } from '@/types';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ==================== 请求拦截器 ====================
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    // 注入 X-Request-ID
    const requestId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2, 18);
    if (config.headers) {
      config.headers['X-Request-ID'] = requestId;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ==================== 响应拦截器 ====================
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error: AxiosError<APIResponse>) => {
    if (error.response?.status === 401) {
      // Token 过期，尝试刷新
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken && error.config && !(error.config as Record<string,unknown>)._retry) {
        (error.config as Record<string,unknown>)._retry = true;
        try {
          const res = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken });
          const { access_token, refresh_token } = res.data.data;
          localStorage.setItem('access_token', access_token);
          localStorage.setItem('refresh_token', refresh_token);
          if (error.config.headers) {
            (error.config.headers as Record<string,string>).Authorization = `Bearer ${access_token}`;
          }
          return api(error.config);
        } catch {
          // 刷新失败，跳转登录
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          window.location.href = '/login';
        }
      } else {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export default api;
