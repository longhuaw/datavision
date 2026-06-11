/**
 * DataVision 系统管理页
 *
 * 功能：
 * - 用户管理：用户列表、新建/编辑/删除用户、重置密码、启用/禁用
 * - 操作日志：审计日志表格、按操作类型和日期范围筛选
 * - 系统信息：应用版本、Python 版本、数据库状态、Redis 状态
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Tabs,
  Table,
  Button,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Space,
  Popconfirm,
  message,
  Card,
  Row,
  Col,
  DatePicker,
  Badge,
  Descriptions,
  Empty,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  LockOutlined,
  StopOutlined,
  CheckCircleOutlined,
  UserOutlined,
  AuditOutlined,
  InfoCircleOutlined,
  SearchOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TablePaginationConfig } from 'antd/es/table';
import dayjs from 'dayjs';
import api from '@/services/api';
import type { APIResponse, PaginatedData, User } from '@/types';

const { RangePicker } = DatePicker;

// ==================== 常量 ====================

const ROLE_CONFIG: Record<string, { color: string; label: string }> = {
  admin: { color: 'red', label: '管理员' },
  editor: { color: 'blue', label: '编辑者' },
  viewer: { color: 'green', label: '观察者' },
  user: { color: 'default', label: '普通用户' },
};

const STATUS_CONFIG: Record<string, { color: string; label: string; badge: 'success' | 'error' | 'processing' | 'default' | 'warning' }> = {
  active: { color: 'green', label: '正常', badge: 'success' },
  disabled: { color: 'red', label: '已禁用', badge: 'error' },
  pending: { color: 'orange', label: '待激活', badge: 'warning' },
};

const ROLE_OPTIONS = [
  { label: '管理员', value: 'admin' },
  { label: '编辑者', value: 'editor' },
  { label: '观察者', value: 'viewer' },
  { label: '普通用户', value: 'user' },
];

const STATUS_OPTIONS = [
  { label: '正常', value: 'active' },
  { label: '已禁用', value: 'disabled' },
  { label: '待激活', value: 'pending' },
];

const ACTION_TYPE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '登录', value: 'login' },
  { label: '登出', value: 'logout' },
  { label: '创建', value: 'create' },
  { label: '更新', value: 'update' },
  { label: '删除', value: 'delete' },
  { label: '查询', value: 'query' },
  { label: '导出', value: 'export' },
];

// ==================== 审计日志类型 ====================

interface AuditLog {
  id: string;
  timestamp: string;
  user: string;
  action_type: string;
  resource_type: string;
  resource_name: string | null;
  ip_address: string;
  status: 'success' | 'failed';
  details?: string;
}

// ==================== 表单类型 ====================

interface CreateUserFormValues {
  username: string;
  password: string;
  email?: string;
  role: string;
}

interface EditUserFormValues {
  username?: string;
  email?: string;
  role: string;
  status: string;
}

// ==================== 健康检查类型 ====================

interface HealthInfo {
  app_version: string;
  python_version: string;
  database: 'connected' | 'disconnected';
  redis: 'connected' | 'disconnected';
  uptime_seconds?: number;
  environment?: string;
}

// ==================== 组件 ====================

const SystemPage: React.FC = () => {
  // ==================== 用户管理状态 ====================
  const [usersLoading, setUsersLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [userPagination, setUserPagination] = useState({ page: 1, pageSize: 10, total: 0 });

  // 新建用户 Modal
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm<CreateUserFormValues>();

  // 编辑用户 Modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [editForm] = Form.useForm<EditUserFormValues>();

  // 重置密码 Modal
  const [resetPwdModalOpen, setResetPwdModalOpen] = useState(false);
  const [resetPwdLoading, setResetPwdLoading] = useState(false);
  const [resetPwdUser, setResetPwdUser] = useState<User | null>(null);
  const [resetPwdForm] = Form.useForm<{ new_password: string; confirm_password: string }>();

  // ==================== 操作日志状态 ====================
  const [logsLoading, setLogsLoading] = useState(false);
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [logPagination, setLogPagination] = useState({ page: 1, pageSize: 10, total: 0 });
  const [actionTypeFilter, setActionTypeFilter] = useState('');
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  // ==================== 系统信息状态 ====================
  const [healthLoading, setHealthLoading] = useState(false);
  const [health, setHealth] = useState<HealthInfo | null>(null);

  // ==================== 数据获取 ====================

  /** 获取用户列表 */
  const fetchUsers = useCallback(async (page = 1, pageSize = 10) => {
    setUsersLoading(true);
    try {
      const res = await api.get<APIResponse<PaginatedData<User>>>('/users', {
        params: { page, page_size: pageSize },
      });

      const { code, message: msg, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '获取用户列表失败');
        return;
      }

      setUsers(data.items);
      setUserPagination({ page: data.page, pageSize: data.page_size, total: data.total });
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setUsersLoading(false);
    }
  }, []);

  /** 获取审计日志 */
  const fetchLogs = useCallback(async (page = 1, pageSize = 10, actionType = '', dates: [dayjs.Dayjs, dayjs.Dayjs] | null = null) => {
    setLogsLoading(true);
    try {
      const params: Record<string, unknown> = {
        page,
        page_size: pageSize,
      };
      if (actionType) {
        params.action_type = actionType;
      }
      if (dates && dates[0] && dates[1]) {
        params.start_time = dates[0].startOf('day').toISOString();
        params.end_time = dates[1].endOf('day').toISOString();
      }

      const res = await api.get<APIResponse<PaginatedData<AuditLog>>>('/users/audit-logs', {
        params,
      });

      const { code, message: msg, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '获取操作日志失败');
        return;
      }

      setLogs(data.items);
      setLogPagination({ page: data.page, pageSize: data.page_size, total: data.total });
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setLogsLoading(false);
    }
  }, []);

  /** 获取系统健康信息 */
  const fetchHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const res = await api.get<APIResponse<HealthInfo>>('/health');
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('获取系统信息失败');
        return;
      }
      setHealth(data);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // ==================== 用户操作 ====================

  /** 新建用户 */
  const handleCreateUser = async (values: CreateUserFormValues) => {
    setCreateLoading(true);
    try {
      const res = await api.post<APIResponse<User>>('/users', {
        username: values.username,
        password: values.password,
        email: values.email || null,
        role: values.role,
      });

      const { code, message: msg } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '创建用户失败');
        return;
      }

      message.success('用户创建成功！');
      setCreateModalOpen(false);
      createForm.resetFields();
      fetchUsers(userPagination.page, userPagination.pageSize);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setCreateLoading(false);
    }
  };

  /** 打开编辑用户 Modal */
  const handleOpenEdit = (user: User) => {
    setEditingUser(user);
    editForm.setFieldsValue({
      email: user.email || '',
      role: user.role,
      status: user.status,
    });
    setEditModalOpen(true);
  };

  /** 提交编辑 */
  const handleEditUser = async (values: EditUserFormValues) => {
    if (!editingUser) return;
    setEditLoading(true);
    try {
      const res = await api.put<APIResponse<User>>(`/users/${editingUser.id}`, {
        email: values.email || null,
        role: values.role,
        status: values.status,
      });

      const { code, message: msg } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '更新用户失败');
        return;
      }

      message.success('用户信息已更新！');
      setEditModalOpen(false);
      fetchUsers(userPagination.page, userPagination.pageSize);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setEditLoading(false);
    }
  };

  /** 删除用户 */
  const handleDeleteUser = async (id: string, username: string) => {
    try {
      const res = await api.delete<APIResponse<null>>(`/users/${id}`);
      const { code, message: msg } = res.data;

      if (code !== 0 && code !== 200) {
        message.error(msg || '删除用户失败');
        return;
      }

      message.success(`用户"${username}"已删除`);
      const newPage = users.length === 1 && userPagination.page > 1
        ? userPagination.page - 1
        : userPagination.page;
      fetchUsers(newPage, userPagination.pageSize);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    }
  };

  /** 禁用 / 启用用户 */
  const handleToggleUserStatus = async (user: User) => {
    const newStatus = user.status === 'disabled' ? 'active' : 'disabled';
    const actionText = newStatus === 'disabled' ? '禁用' : '启用';
    try {
      const res = await api.put<APIResponse<User>>(`/users/${user.id}`, {
        email: user.email,
        role: user.role,
        status: newStatus,
      });

      const { code, message: msg } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || `${actionText}用户失败`);
        return;
      }

      message.success(`用户已${actionText}`);
      fetchUsers(userPagination.page, userPagination.pageSize);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    }
  };

  /** 打开重置密码 Modal */
  const handleOpenResetPwd = (user: User) => {
    setResetPwdUser(user);
    resetPwdForm.resetFields();
    setResetPwdModalOpen(true);
  };

  /** 提交重置密码 */
  const handleResetPassword = async (values: { new_password: string; confirm_password: string }) => {
    if (!resetPwdUser) return;
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入密码不一致');
      return;
    }
    setResetPwdLoading(true);
    try {
      const res = await api.put<APIResponse<null>>(`/users/${resetPwdUser.id}/reset-password`, {
        new_password: values.new_password,
      });

      const { code, message: msg } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '重置密码失败');
        return;
      }

      message.success('密码重置成功！');
      setResetPwdModalOpen(false);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setResetPwdLoading(false);
    }
  };

  // ==================== 表格列定义 ====================

  /** 用户表格列 */
  const userColumns: ColumnsType<User> = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      width: 140,
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      width: 200,
      ellipsis: true,
      render: (text: string | null) => text || <span style={{ color: '#999' }}>-</span>,
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (role: string) => {
        const cfg = ROLE_CONFIG[role] || { color: 'default', label: role };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const cfg = STATUS_CONFIG[status] || { color: 'default', label: status, badge: 'default' as const };
        return <Badge status={cfg.badge} text={cfg.label} />;
      },
    },
    {
      title: '最后登录',
      dataIndex: 'last_login_at',
      key: 'last_login_at',
      width: 180,
      render: (text: string | null) =>
        text ? dayjs(text).format('YYYY-MM-DD HH:mm:ss') : <span style={{ color: '#999' }}>从未登录</span>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      fixed: 'right',
      render: (_: unknown, record: User) => (
        <Space size="small">
          {/* 编辑 */}
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleOpenEdit(record)}
          >
            编辑
          </Button>

          {/* 禁用 / 启用 */}
          <Popconfirm
            title={record.status === 'disabled' ? '确认启用' : '确认禁用'}
            description={
              record.status === 'disabled'
                ? `确定要启用用户"${record.username}"吗？`
                : `确定要禁用用户"${record.username}"吗？禁用后该用户将无法登录。`
            }
            onConfirm={() => handleToggleUserStatus(record)}
            okText="确认"
            cancelText="取消"
            okButtonProps={record.status !== 'disabled' ? { danger: true } : undefined}
          >
            <Button
              type="link"
              size="small"
              icon={<StopOutlined />}
              danger={record.status !== 'disabled'}
            >
              {record.status === 'disabled' ? '启用' : '禁用'}
            </Button>
          </Popconfirm>

          {/* 重置密码 */}
          <Button
            type="link"
            size="small"
            icon={<LockOutlined />}
            onClick={() => handleOpenResetPwd(record)}
          >
            重置密码
          </Button>

          {/* 删除 */}
          <Popconfirm
            title="确认删除"
            description={`确定要删除用户"${record.username}"吗？此操作不可恢复。`}
            onConfirm={() => handleDeleteUser(record.id, record.username)}
            okText="确认删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  /** 操作日志表格列 */
  const logColumns: ColumnsType<AuditLog> = [
    {
      title: '时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      width: 180,
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '用户',
      dataIndex: 'user',
      key: 'user',
      width: 120,
    },
    {
      title: '操作类型',
      dataIndex: 'action_type',
      key: 'action_type',
      width: 120,
      render: (type: string) => {
        const typeMap: Record<string, { color: string; label: string }> = {
          login: { color: 'green', label: '登录' },
          logout: { color: 'default', label: '登出' },
          create: { color: 'blue', label: '创建' },
          update: { color: 'orange', label: '更新' },
          delete: { color: 'red', label: '删除' },
          query: { color: 'cyan', label: '查询' },
          export: { color: 'purple', label: '导出' },
        };
        const cfg = typeMap[type] || { color: 'default', label: type };
        return <Tag color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '资源类型',
      dataIndex: 'resource_type',
      key: 'resource_type',
      width: 120,
    },
    {
      title: '资源名称',
      dataIndex: 'resource_name',
      key: 'resource_name',
      width: 180,
      ellipsis: true,
      render: (text: string | null) => text || <span style={{ color: '#999' }}>-</span>,
    },
    {
      title: 'IP',
      dataIndex: 'ip_address',
      key: 'ip_address',
      width: 140,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) =>
        status === 'success' ? (
          <Tag color="green" icon={<CheckCircleOutlined />}>成功</Tag>
        ) : (
          <Tag color="red">失败</Tag>
        ),
    },
  ];

  // ==================== 分页处理 ====================

  const handleUserTableChange = (pag: TablePaginationConfig) => {
    fetchUsers(pag.current || 1, pag.pageSize || 10);
  };

  const handleLogTableChange = (pag: TablePaginationConfig) => {
    fetchLogs(pag.current || 1, pag.pageSize || 10, actionTypeFilter, dateRange);
  };

  // ==================== 操作日志筛选 ====================

  const handleLogSearch = () => {
    fetchLogs(1, logPagination.pageSize, actionTypeFilter, dateRange);
  };

  const handleLogReset = () => {
    setActionTypeFilter('');
    setDateRange(null);
    fetchLogs(1, logPagination.pageSize);
  };

  // ==================== Tab 项 ====================

  const tabItems = [
    // ---------- 用户管理 ----------
    {
      key: 'users',
      label: (
        <span>
          <UserOutlined />
          用户管理
        </span>
      ),
      children: (
        <div>
          {/* 用户操作栏 */}
          <Card
            styles={{ body: { padding: '16px 24px' } }}
            style={{ marginBottom: 16 }}
          >
            <Row justify="space-between" align="middle">
              <Col>
                <Space size={12}>
                  <UserOutlined style={{ fontSize: 20 }} />
                  <span style={{ fontSize: 16, fontWeight: 600 }}>用户列表</span>
                </Space>
              </Col>
              <Col>
                <Space>
                  <Button
                    icon={<ReloadOutlined />}
                    onClick={() => fetchUsers(userPagination.page, userPagination.pageSize)}
                  >
                    刷新
                  </Button>
                  <Button
                    type="primary"
                    icon={<PlusOutlined />}
                    onClick={() => {
                      createForm.resetFields();
                      setCreateModalOpen(true);
                    }}
                  >
                    新建用户
                  </Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* 用户表格 */}
          <Card styles={{ body: { padding: 0 } }}>
            <Table<User>
              rowKey="id"
              columns={userColumns}
              dataSource={users}
              loading={usersLoading}
              pagination={{
                current: userPagination.page,
                pageSize: userPagination.pageSize,
                total: userPagination.total,
                showSizeChanger: true,
                showQuickJumper: true,
                pageSizeOptions: ['10', '20', '50'],
                showTotal: (total: number) => `共 ${total} 个用户`,
              }}
              onChange={handleUserTableChange}
              scroll={{ x: 1120 }}
              locale={{
                emptyText: (
                  <div style={{ padding: '60px 0' }}>
                    <UserOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                    <p style={{ marginTop: 16, color: '#999' }}>暂无用户</p>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => {
                        createForm.resetFields();
                        setCreateModalOpen(true);
                      }}
                    >
                      新建用户
                    </Button>
                  </div>
                ),
              }}
            />
          </Card>
        </div>
      ),
    },

    // ---------- 操作日志 ----------
    {
      key: 'logs',
      label: (
        <span>
          <AuditOutlined />
          操作日志
        </span>
      ),
      children: (
        <div>
          {/* 筛选栏 */}
          <Card
            styles={{ body: { padding: '16px 24px' } }}
            style={{ marginBottom: 16 }}
          >
            <Row justify="space-between" align="middle">
              <Col>
                <Space size={12}>
                  <AuditOutlined style={{ fontSize: 20 }} />
                  <span style={{ fontSize: 16, fontWeight: 600 }}>操作日志</span>
                </Space>
              </Col>
              <Col>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => fetchLogs(logPagination.page, logPagination.pageSize, actionTypeFilter, dateRange)}
                >
                  刷新
                </Button>
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 12 }} align="middle">
              <Col>
                <Select
                  placeholder="操作类型"
                  allowClear
                  value={actionTypeFilter || undefined}
                  onChange={(val) => setActionTypeFilter(val || '')}
                  options={ACTION_TYPE_OPTIONS}
                  style={{ width: 140 }}
                />
              </Col>
              <Col>
                <RangePicker
                  value={dateRange}
                  onChange={(dates) => setDateRange(dates as [dayjs.Dayjs, dayjs.Dayjs] | null)}
                  allowClear
                  placeholder={['开始时间', '结束时间']}
                />
              </Col>
              <Col>
                <Space>
                  <Button
                    type="primary"
                    icon={<SearchOutlined />}
                    onClick={handleLogSearch}
                  >
                    查询
                  </Button>
                  <Button onClick={handleLogReset}>重置</Button>
                </Space>
              </Col>
            </Row>
          </Card>

          {/* 日志表格 */}
          <Card styles={{ body: { padding: 0 } }}>
            <Table<AuditLog>
              rowKey="id"
              columns={logColumns}
              dataSource={logs}
              loading={logsLoading}
              pagination={{
                current: logPagination.page,
                pageSize: logPagination.pageSize,
                total: logPagination.total,
                showSizeChanger: true,
                showQuickJumper: true,
                pageSizeOptions: ['10', '20', '50'],
                showTotal: (total: number) => `共 ${total} 条日志`,
              }}
              onChange={handleLogTableChange}
              scroll={{ x: 960 }}
              locale={{
                emptyText: (
                  <div style={{ padding: '60px 0' }}>
                    <AuditOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                    <p style={{ marginTop: 16, color: '#999' }}>暂无操作日志</p>
                  </div>
                ),
              }}
            />
          </Card>
        </div>
      ),
    },

    // ---------- 系统信息 ----------
    {
      key: 'info',
      label: (
        <span>
          <InfoCircleOutlined />
          系统信息
        </span>
      ),
      children: (
        <div>
          {/* 系统信息头部 */}
          <Card
            styles={{ body: { padding: '16px 24px' } }}
            style={{ marginBottom: 16 }}
          >
            <Row justify="space-between" align="middle">
              <Col>
                <Space size={12}>
                  <InfoCircleOutlined style={{ fontSize: 20 }} />
                  <span style={{ fontSize: 16, fontWeight: 600 }}>系统信息</span>
                </Space>
              </Col>
              <Col>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={fetchHealth}
                  loading={healthLoading}
                >
                  刷新
                </Button>
              </Col>
            </Row>
          </Card>

          {/* 系统信息卡片 */}
          <Row gutter={[16, 16]}>
            {!healthLoading && health ? (
              <>
                <Col xs={24} sm={12}>
                  <Card>
                    <Descriptions
                      title="应用信息"
                      column={1}
                      colon={false}
                      size="small"
                    >
                      <Descriptions.Item label="应用版本">
                        <Tag color="blue">{health.app_version}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="Python 版本">
                        <Tag>{health.python_version}</Tag>
                      </Descriptions.Item>
                      {health.environment && (
                        <Descriptions.Item label="运行环境">
                          <Tag color="cyan">{health.environment}</Tag>
                        </Descriptions.Item>
                      )}
                      {health.uptime_seconds !== undefined && (
                        <Descriptions.Item label="运行时长">
                          {formatUptime(health.uptime_seconds)}
                        </Descriptions.Item>
                      )}
                    </Descriptions>
                  </Card>
                </Col>

                <Col xs={24} sm={12}>
                  <Card>
                    <Descriptions
                      title="服务状态"
                      column={1}
                      colon={false}
                      size="small"
                    >
                      <Descriptions.Item label="数据库状态">
                        {health.database === 'connected' ? (
                          <Tag color="green" icon={<CheckCircleOutlined />}>已连接</Tag>
                        ) : (
                          <Tag color="red">未连接</Tag>
                        )}
                      </Descriptions.Item>
                      <Descriptions.Item label="Redis 状态">
                        {health.redis === 'connected' ? (
                          <Tag color="green" icon={<CheckCircleOutlined />}>已连接</Tag>
                        ) : (
                          <Tag color="red">未连接</Tag>
                        )}
                      </Descriptions.Item>
                    </Descriptions>
                  </Card>
                </Col>
              </>
            ) : healthLoading ? (
              <Col span={24}>
                <Card>
                  <div style={{ textAlign: 'center', padding: '60px 0', color: '#999' }}>
                    <InfoCircleOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
                    <p>加载系统信息中...</p>
                  </div>
                </Card>
              </Col>
            ) : (
              <Col span={24}>
                <Card>
                  <Empty
                    image={<SettingOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
                    description="暂无系统信息"
                  >
                    <Button type="primary" onClick={fetchHealth}>
                      获取系统信息
                    </Button>
                  </Empty>
                </Card>
              </Col>
            )}
          </Row>
        </div>
      ),
    },
  ];

  // ==================== 渲染 ====================

  return (
    <div style={{ padding: 24, height: '100%' }}>
      {/* 页面标题 */}
      <Card
        styles={{ body: { padding: '16px 24px' } }}
        style={{ marginBottom: 16 }}
      >
        <Space size={12}>
          <SettingOutlined style={{ fontSize: 20 }} />
          <span style={{ fontSize: 18, fontWeight: 600 }}>系统管理</span>
        </Space>
      </Card>

      {/* Tabs */}
      <Card styles={{ body: { padding: '0 24px 24px' } }}>
        <Tabs
          defaultActiveKey="users"
          items={tabItems}
          style={{ marginTop: 0 }}
          tabBarStyle={{ marginBottom: 24 }}
        />
      </Card>

      {/* ========== 新建用户 Modal ========== */}
      <Modal
        title="新建用户"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          createForm.resetFields();
        }}
        footer={null}
        destroyOnClose
        width={520}
      >
        <Form<CreateUserFormValues>
          form={createForm}
          layout="vertical"
          onFinish={handleCreateUser}
          initialValues={{ role: 'user' }}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少 3 个字符' },
              { max: 32, message: '用户名不能超过 32 个字符' },
            ]}
          >
            <Input placeholder="请输入用户名" maxLength={32} />
          </Form.Item>

          <Form.Item
            name="email"
            label="邮箱"
            rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}
          >
            <Input placeholder="请输入邮箱（选填）" />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少 6 个字符' },
            ]}
          >
            <Input.Password placeholder="请输入密码" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="请选择角色" options={ROLE_OPTIONS} />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setCreateModalOpen(false);
                  createForm.resetFields();
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={createLoading}>
                {createLoading ? '创建中...' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* ========== 编辑用户 Modal ========== */}
      <Modal
        title="编辑用户"
        open={editModalOpen}
        onCancel={() => {
          setEditModalOpen(false);
          setEditingUser(null);
        }}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form<EditUserFormValues>
          form={editForm}
          layout="vertical"
          onFinish={handleEditUser}
          style={{ marginTop: 16 }}
        >
          <Form.Item name="username" label="用户名">
            <Input disabled placeholder={editingUser?.username} />
          </Form.Item>

          <Form.Item
            name="email"
            label="邮箱"
            rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}
          >
            <Input placeholder="请输入邮箱" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="请选择角色" options={ROLE_OPTIONS} />
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
            rules={[{ required: true, message: '请选择状态' }]}
          >
            <Select placeholder="请选择状态" options={STATUS_OPTIONS} />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setEditModalOpen(false);
                  setEditingUser(null);
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={editLoading}>
                {editLoading ? '保存中...' : '保存'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* ========== 重置密码 Modal ========== */}
      <Modal
        title="重置密码"
        open={resetPwdModalOpen}
        onCancel={() => {
          setResetPwdModalOpen(false);
          setResetPwdUser(null);
        }}
        footer={null}
        destroyOnClose
        width={440}
      >
        <div style={{ marginBottom: 16, color: '#666' }}>
          为用户 <Tag>{resetPwdUser?.username}</Tag> 重置密码
        </div>
        <Form
          form={resetPwdForm}
          layout="vertical"
          onFinish={handleResetPassword}
          style={{ marginTop: 8 }}
        >
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少 6 个字符' },
            ]}
          >
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>

          <Form.Item
            name="confirm_password"
            label="确认密码"
            rules={[
              { required: true, message: '请确认新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setResetPwdModalOpen(false);
                  setResetPwdUser(null);
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={resetPwdLoading}>
                {resetPwdLoading ? '重置中...' : '确认重置'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

/** 格式化运行时长 */
function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (days > 0) parts.push(`${days} 天`);
  if (hours > 0) parts.push(`${hours} 小时`);
  if (minutes > 0) parts.push(`${minutes} 分钟`);
  if (parts.length === 0) parts.push(`${seconds} 秒`);
  return parts.join(' ');
}

export default SystemPage;
