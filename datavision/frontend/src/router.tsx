/**
 * React Router 路由配置
 */
import { createBrowserRouter, Navigate } from 'react-router-dom';
import MainLayout from '@/layouts/MainLayout';
import AuthLayout from '@/layouts/AuthLayout';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import ChartWorkbench from '@/pages/ChartWorkbench';
import Designer from '@/pages/Designer';
import Datasource from '@/pages/Datasource';
import Dataset from '@/pages/Dataset';
import AIAssistant from '@/pages/AIAssistant';
import System from '@/pages/System';

// 简单的鉴权守卫组件
import { useAuthStore } from '@/store';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

const router = createBrowserRouter([
  {
    path: '/login',
    element: <AuthLayout />,
    children: [
      { index: true, element: <Login /> },
    ],
  },
  {
    path: '/',
    element: (
      <AuthGuard>
        <MainLayout />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboards" replace /> },
      { path: 'dashboards', element: <Dashboard /> },
      { path: 'dashboards/:id', element: <Designer /> },
      { path: 'charts', element: <ChartWorkbench /> },
      { path: 'charts/:id', element: <ChartWorkbench /> },
      { path: 'datasources', element: <Datasource /> },
      { path: 'datasets', element: <Dataset /> },
      { path: 'ai', element: <AIAssistant /> },
      { path: 'system', element: <System /> },
    ],
  },
  {
    // 公开看板查看
    path: '/view/:token',
    element: <Designer />,
  },
]);

export default router;
