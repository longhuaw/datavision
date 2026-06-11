/**
 * DataVision 登录页
 *
 * 功能：
 * - 用户名 / 密码登录
 * - "记住我"（将凭据存入 localStorage 提示符）
 * - 登录成功后存储 token 并跳转到首页
 * - 失败时展示错误信息
 * - 可跳转到注册页
 */

import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Form, Input, Button, Checkbox, Card, message, Space } from 'antd';
import { UserOutlined, LockOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useAuthStore } from '@/store';
import api from '@/services/api';
import type { APIResponse, TokenResponse, User } from '@/types';

interface LoginFormValues {
  username: string;
  password: string;
  remember: boolean;
}

const Login: React.FC = () => {
  const navigate = useNavigate();
  const loginStore = useAuthStore((s) => s.login);
  const [loading, setLoading] = useState(false);
  const [form] = Form.useForm<LoginFormValues>();

  /**
   * 表单提交处理
   */
  const handleSubmit = async (values: LoginFormValues) => {
    setLoading(true);
    try {
      // 1. 调用登录接口
      const loginRes = await api.post<APIResponse<TokenResponse & { user?: User }>>(
        '/auth/login',
        {
          username: values.username,
          password: values.password,
        },
      );

      const { code, message: msg, data } = loginRes.data;

      if (code !== 0 && code !== 200) {
        throw new Error(msg || '登录失败，请检查用户名和密码');
      }

      // 2. 存储 token
      const { access_token, refresh_token } = data;

      // 3. 如果登录响应中已包含用户信息，直接使用；否则发起 /me 请求
      let user: User;
      if (data.user) {
        user = data.user;
      } else {
        const meRes = await api.get<APIResponse<User>>('/auth/me', {
          headers: { Authorization: `Bearer ${access_token}` },
        });
        user = meRes.data.data;
      }

      // 4. 写入全局状态（内部会写 localStorage）
      loginStore(access_token, refresh_token, user);

      message.success(`欢迎回来，${user.nickname || user.username}！`);
      navigate('/', { replace: true });
    } catch (err: unknown) {
      const errorMessage =
        (err as { message?: string })?.message || '网络异常，请稍后重试';

      // 如果 Axios 拦截器已经弹到 /login 了，就不重复提示
      const axiosErr = err as { response?: { status?: number } };
      if (axiosErr?.response?.status === 401 || axiosErr?.response?.status === 401) {
        message.error('用户名或密码错误');
      } else {
        message.error(errorMessage);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="dv-login-card dv-fade-in" bordered={false}>
      {/* ── 头部 ── */}
      <div className="dv-login-header">
        <Space align="center" size={12}>
          <ThunderboltOutlined style={{ fontSize: 32 }} />
          <h1>DataVision</h1>
        </Space>
        <p>智能数据可视化低代码平台</p>
      </div>

      {/* ── 表单 ── */}
      <div className="dv-login-form">
        <Form<LoginFormValues>
          form={form}
          onFinish={handleSubmit}
          initialValues={{ remember: true }}
          size="large"
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<UserOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
              placeholder="用户名"
              autoFocus
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined style={{ color: 'rgba(0,0,0,.25)' }} />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Form.Item name="remember" valuePropName="checked" noStyle>
                <Checkbox>记住我</Checkbox>
              </Form.Item>

              <Link to="/register" style={{ fontSize: 14, color: '#1677ff' }}>
                注册账号
              </Link>
            </div>
          </Form.Item>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={loading}
              block
              style={{ height: 44, fontSize: 16 }}
            >
              {loading ? '登录中...' : '登 录'}
            </Button>
          </Form.Item>
        </Form>
      </div>
    </Card>
  );
};

export default Login;
