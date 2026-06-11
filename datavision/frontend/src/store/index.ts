/**
 * Zustand 全局状态管理
 */
import { create } from 'zustand';
import type { User } from '@/types';

// ==================== 认证状态 ====================
interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: User | null;
  isAuthenticated: boolean;
  login: (token: string, refreshToken: string, user: User) => void;
  logout: () => void;
  updateUser: (user: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  user: null,
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: (token, refreshToken, user) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('refresh_token', refreshToken);
    set({ token, refreshToken, user, isAuthenticated: true });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    set({ token: null, refreshToken: null, user: null, isAuthenticated: false });
  },

  updateUser: (updates) => {
    set((state) => ({
      user: state.user ? { ...state.user, ...updates } : null,
    }));
  },
}));

// ==================== 全局配置状态 ====================
interface AppState {
  collapsed: boolean;
  theme: 'light' | 'dark';
  toggleCollapsed: () => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useAppStore = create<AppState>((set) => ({
  collapsed: false,
  theme: (localStorage.getItem('dv-theme') as 'light' | 'dark') || 'light',

  toggleCollapsed: () => set((state) => ({ collapsed: !state.collapsed })),

  setTheme: (theme) => {
    localStorage.setItem('dv-theme', theme);
    set({ theme });
  },
}));
