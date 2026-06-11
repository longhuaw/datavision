/**
 * DataVision 数据源管理页
 *
 * 功能：
 * - 数据源卡片网格展示（含名称、类型图标、状态徽章、描述、创建时间）
 * - 新建数据源（4 步 Modal：选类型 → 配置连接 → 测试连接 → 命名保存）
 * - 编辑 / 测试连接 / 同步元数据 / 删除 操作
 * - 加载态 / 空状态
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  Button,
  Modal,
  Steps,
  Form,
  Input,
  InputNumber,
  Select,
  Tag,
  Space,
  message,
  Row,
  Col,
  Spin,
  Popconfirm,
  Upload,
  Empty,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  LinkOutlined,
  SyncOutlined,
  ApiOutlined,
  FileExcelOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import api from '@/services/api';
import type { APIResponse, DataSource, DataSourceType } from '@/types';

// ==================== 类型图标映射 ====================

const TYPE_CONFIG: Record<
  DataSourceType,
  { icon: React.ReactNode; label: string; color: string }
> = {
  mysql: {
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#4479A1' }} />,
    label: 'MySQL',
    color: '#4479A1',
  },
  postgresql: {
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#336791' }} />,
    label: 'PostgreSQL',
    color: '#336791',
  },
  clickhouse: {
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#F7C919' }} />,
    label: 'ClickHouse',
    color: '#F7C919',
  },
  api: {
    icon: <ApiOutlined style={{ fontSize: 28, color: '#722ED1' }} />,
    label: 'API',
    color: '#722ED1',
  },
  excel: {
    icon: <FileExcelOutlined style={{ fontSize: 28, color: '#52C41A' }} />,
    label: 'Excel',
    color: '#52C41A',
  },
  sqlite: {
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#003B57' }} />,
    label: 'SQLite',
    color: '#003B57',
  },
  mssql: {
    icon: <DatabaseOutlined style={{ fontSize: 28, color: '#CC2927' }} />,
    label: 'SQL Server',
    color: '#CC2927',
  },
};

const STATUS_CONFIG: Record<string, { color: string; text: string; icon: React.ReactNode }> = {
  active: {
    color: 'green',
    text: '正常',
    icon: <CheckCircleOutlined />,
  },
  error: {
    color: 'red',
    text: '异常',
    icon: <CloseCircleOutlined />,
  },
  disabled: {
    color: 'default',
    text: '已禁用',
    icon: <MinusCircleOutlined />,
  },
};

// 可新建的数据源类型
const SELECTABLE_TYPES: DataSourceType[] = ['mysql', 'postgresql', 'clickhouse', 'api', 'excel'];

const AUTH_TYPE_OPTIONS = [
  { label: '无认证', value: 'none' },
  { label: 'Basic Auth', value: 'basic' },
  { label: 'Bearer Token', value: 'bearer' },
  { label: 'API Key', value: 'api_key' },
  { label: 'OAuth 2.0', value: 'oauth2' },
];

const METHOD_OPTIONS = [
  { label: 'GET', value: 'GET' },
  { label: 'POST', value: 'POST' },
  { label: 'PUT', value: 'PUT' },
  { label: 'DELETE', value: 'DELETE' },
];

// ==================== 表单类型 ====================

interface HeaderItem {
  key: string;
  value: string;
}

interface ConnectionConfig {
  // MySQL / PostgreSQL / ClickHouse
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  schema?: string; // PostgreSQL
  // API
  base_url?: string;
  method?: string;
  headers?: HeaderItem[];
  auth_type?: string;
  auth_username?: string;
  auth_password?: string;
  auth_token?: string;
  auth_key?: string;
  auth_value?: string;
  // Excel - handled by Upload
  file?: File;
}

interface CreateFormValues {
  name: string;
  description: string;
  // connection config fields are stored directly too
  host?: string;
  port?: number;
  database?: string;
  username?: string;
  password?: string;
  schema?: string;
  base_url?: string;
  method?: string;
  auth_type?: string;
  auth_username?: string;
  auth_password?: string;
  auth_token?: string;
  auth_key?: string;
  auth_value?: string;
}

// ==================== 组件 ====================

const DatasourcePage: React.FC = () => {
  // ---------- 列表状态 ----------
  const [loading, setLoading] = useState(false);
  const [datasources, setDatasources] = useState<DataSource[]>([]);

  // ---------- 新建 Modal 状态 ----------
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createStep, setCreateStep] = useState(0);
  const [selectedType, setSelectedType] = useState<DataSourceType | null>(null);
  const [createLoading, setCreateLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [form] = Form.useForm<CreateFormValues>();
  const [headers, setHeaders] = useState<HeaderItem[]>([{ key: '', value: '' }]);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [authTypeKey, setAuthTypeKey] = useState(0); // force re-render auth conditional fields

  // ---------- 编辑 Modal 状态 ----------
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editingRecord, setEditingRecord] = useState<DataSource | null>(null);
  const [editForm] = Form.useForm();

  // ==================== 数据获取 ====================

  const fetchDatasources = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<APIResponse<DataSource[]>>('/datasources');
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('获取数据源列表失败');
        return;
      }
      setDatasources(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDatasources();
  }, [fetchDatasources]);

  // ==================== 新建 - 步骤控制 ====================

  const openCreateModal = () => {
    setCreateStep(0);
    setSelectedType(null);
    setTestResult(null);
    form.resetFields();
    setHeaders([{ key: '', value: '' }]);
    setUploadedFile(null);
    setAuthTypeKey(0);
    setCreateModalOpen(true);
  };

  const stepsItems = [
    { title: '选择类型' },
    { title: '配置连接' },
    { title: '测试连接' },
    { title: '基本信息' },
  ];

  const handleSelectType = (type: DataSourceType) => {
    setSelectedType(type);
    setCreateStep(1);
  };

  const handleNextFromConfig = () => {
    // Validate dynamic fields before proceeding
    form
      .validateFields()
      .then(() => {
        setTestResult(null);
        setCreateStep(2);
      })
      .catch(() => {
        // validation errors shown by antd
      });
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const config = buildConnectionConfig();
      const res = await api.post<APIResponse<{ success: boolean; message: string }>>(
        '/datasources/test',
        {
          type: selectedType,
          config,
        },
      );
      const { code, data } = res.data;
      if (code === 0 || code === 200) {
        setTestResult(data ?? { success: true, message: '连接测试成功！' });
      } else {
        setTestResult({
          success: false,
          message: (res.data as { message?: string })?.message || '连接测试失败',
        });
      }
    } catch (err: unknown) {
      // API error - treat as test failure
      const msg = (err as { response?: { data?: { message?: string } }; message?: string })?.response
        ?.data?.message;
      setTestResult({
        success: false,
        message: msg || (err as { message?: string })?.message || '连接测试失败，请检查配置',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleNextToInfo = () => {
    setCreateStep(3);
  };

  const handlePrevStep = () => {
    if (createStep === 1) {
      setCreateStep(0);
      setSelectedType(null);
    } else {
      setCreateStep(createStep - 1);
    }
  };

  // ==================== 构建连接配置 ====================

  const buildConnectionConfig = (): Record<string, unknown> => {
    const values = form.getFieldsValue();
    let config: Record<string, unknown> = {};

    if (selectedType === 'mysql' || selectedType === 'clickhouse') {
      config = {
        host: values.host,
        port: values.port,
        database: values.database,
        username: values.username,
        password: values.password,
      };
    } else if (selectedType === 'postgresql') {
      config = {
        host: values.host,
        port: values.port,
        database: values.database,
        username: values.username,
        password: values.password,
        schema: values.schema || 'public',
      };
    } else if (selectedType === 'api') {
      const cleanedHeaders: Record<string, string> = {};
      headers.forEach((h) => {
        if (h.key.trim()) {
          cleanedHeaders[h.key.trim()] = h.value;
        }
      });

      config = {
        base_url: values.base_url,
        method: values.method || 'GET',
        headers: cleanedHeaders,
        auth_type: values.auth_type || 'none',
        auth_username: values.auth_username,
        auth_password: values.auth_password,
        auth_token: values.auth_token,
        auth_key: values.auth_key,
        auth_value: values.auth_value,
      };
    } else if (selectedType === 'excel') {
      config = {
        file_name: uploadedFile?.name || '',
      };
    }

    return config;
  };

  // ==================== 新建数据源 ====================

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      setCreateLoading(true);

      const config = buildConnectionConfig();

      const res = await api.post<APIResponse<DataSource>>('/datasources', {
        name: values.name,
        description: values.description || '',
        type: selectedType,
        config,
      });

      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('创建数据源失败');
        return;
      }

      message.success('数据源创建成功！');
      setCreateModalOpen(false);
      fetchDatasources();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) {
        // form validation error, already shown
        return;
      }
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setCreateLoading(false);
    }
  };

  // ==================== 操作 ====================

  const handleDelete = async (id: string) => {
    try {
      const res = await api.delete<APIResponse<null>>(`/datasources/${id}`);
      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('删除失败');
        return;
      }
      message.success('数据源已删除');
      fetchDatasources();
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    }
  };

  const handleTestExisting = async (record: DataSource) => {
    message.loading({ content: '正在测试连接...', key: 'test-existing' });
    try {
      const res = await api.post<APIResponse<{ success: boolean; message: string }>>(
        '/datasources/test',
        {
          type: record.type,
          config: record.config,
        },
      );
      const { code, data } = res.data;
      if (code === 0 || code === 200) {
        message.success({ content: data?.message || '连接测试成功！', key: 'test-existing' });
      } else {
        message.error({
          content: (res.data as { message?: string })?.message || '连接测试失败',
          key: 'test-existing',
        });
      }
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data
          ?.message;
      message.error({
        content: msg || (err as { message?: string })?.message || '连接测试失败',
        key: 'test-existing',
      });
    }
  };

  const handleSyncMetadata = async (record: DataSource) => {
    message.loading({ content: '正在同步元数据...', key: 'sync-meta' });
    try {
      const res = await api.post<APIResponse<null>>(`/datasources/${record.id}/sync-metadata`);
      const { code } = res.data;
      if (code === 0 || code === 200) {
        message.success({ content: '元数据同步成功！', key: 'sync-meta' });
        fetchDatasources();
      } else {
        message.error({
          content: (res.data as { message?: string })?.message || '同步失败',
          key: 'sync-meta',
        });
      }
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error({ content: errorMessage, key: 'sync-meta' });
    }
  };

  const handleEdit = (record: DataSource) => {
    setEditingRecord(record);
    editForm.setFieldsValue({
      name: record.name,
      description: record.description,
    });
    setEditModalOpen(true);
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      if (!editingRecord) return;
      setEditLoading(true);

      const res = await api.put<APIResponse<DataSource>>(`/datasources/${editingRecord.id}`, {
        ...editingRecord,
        name: values.name,
        description: values.description || '',
      });

      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('更新失败');
        return;
      }
      message.success('数据源更新成功！');
      setEditModalOpen(false);
      fetchDatasources();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setEditLoading(false);
    }
  };

  // ==================== 渲染动态连接配置表单 ====================

  const renderConnectionForm = () => {
    if (selectedType === 'mysql' || selectedType === 'clickhouse') {
      return (
        <>
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item
                name="host"
                label="主机地址"
                rules={[{ required: true, message: '请输入主机地址' }]}
              >
                <Input placeholder="例如：127.0.0.1 或 db.example.com" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="port"
                label="端口"
                rules={[{ required: true, message: '请输入端口' }]}
                initialValue={selectedType === 'mysql' ? 3306 : 8123}
              >
                <InputNumber min={1} max={65535} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="database"
            label="数据库名"
            rules={[{ required: true, message: '请输入数据库名' }]}
          >
            <Input placeholder="请输入数据库名" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input placeholder="请输入用户名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="请输入密码" />
              </Form.Item>
            </Col>
          </Row>
        </>
      );
    }

    if (selectedType === 'postgresql') {
      return (
        <>
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item
                name="host"
                label="主机地址"
                rules={[{ required: true, message: '请输入主机地址' }]}
              >
                <Input placeholder="例如：127.0.0.1 或 db.example.com" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="port"
                label="端口"
                rules={[{ required: true, message: '请输入端口' }]}
                initialValue={5432}
              >
                <InputNumber min={1} max={65535} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item
            name="database"
            label="数据库名"
            rules={[{ required: true, message: '请输入数据库名' }]}
          >
            <Input placeholder="请输入数据库名" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input placeholder="请输入用户名" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="请输入密码" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="schema" label="Schema" initialValue="public">
            <Input placeholder="默认 public" />
          </Form.Item>
        </>
      );
    }

    if (selectedType === 'api') {
      return (
        <>
          <Row gutter={16}>
            <Col span={16}>
              <Form.Item
                name="base_url"
                label="Base URL"
                rules={[{ required: true, message: '请输入接口地址' }]}
              >
                <Input placeholder="https://api.example.com/v1" />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item
                name="method"
                label="请求方法"
                rules={[{ required: true, message: '请选择' }]}
                initialValue="GET"
              >
                <Select options={METHOD_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>

          {/* Headers Key-Value Editor */}
          <Form.Item label="请求头 (Headers)">
            {headers.map((item, idx) => (
              <Row
                gutter={8}
                key={idx}
                style={{ marginBottom: idx < headers.length - 1 ? 8 : 0 }}
              >
                <Col span={10}>
                  <Input
                    placeholder="Header Key"
                    value={item.key}
                    onChange={(e) => {
                      const next = [...headers];
                      next[idx] = { ...next[idx], key: e.target.value };
                      setHeaders(next);
                    }}
                  />
                </Col>
                <Col span={10}>
                  <Input
                    placeholder="Header Value"
                    value={item.value}
                    onChange={(e) => {
                      const next = [...headers];
                      next[idx] = { ...next[idx], value: e.target.value };
                      setHeaders(next);
                    }}
                  />
                </Col>
                <Col span={4}>
                  <Button
                    danger
                    disabled={headers.length === 1}
                    onClick={() => {
                      const next = headers.filter((_, i) => i !== idx);
                      setHeaders(next.length ? next : [{ key: '', value: '' }]);
                    }}
                    icon={<DeleteOutlined />}
                  />
                </Col>
              </Row>
            ))}
            <Button
              type="dashed"
              size="small"
              onClick={() => setHeaders([...headers, { key: '', value: '' }])}
              style={{ marginTop: 8 }}
              block
              icon={<PlusOutlined />}
            >
              添加请求头
            </Button>
          </Form.Item>

          <Form.Item name="auth_type" label="认证方式" initialValue="none">
            <Select
              options={AUTH_TYPE_OPTIONS}
              onChange={(val: string) => {
                // Clear auth fields when changing type
                form.setFieldsValue({
                  auth_username: undefined,
                  auth_password: undefined,
                  auth_token: undefined,
                  auth_key: undefined,
                  auth_value: undefined,
                });
                setAuthTypeKey((k) => k + 1); // force re-render conditional fields
              }}
            />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.auth_type !== cur.auth_type}>
            {({ getFieldValue }) => {
              const authType = getFieldValue('auth_type') || 'none';
              if (authType === 'basic') {
                return (
                  <Row gutter={16}>
                    <Col span={12}>
                      <Form.Item
                        name="auth_username"
                        label="用户名"
                        rules={[{ required: true, message: '请输入用户名' }]}
                      >
                        <Input placeholder="Basic Auth 用户名" />
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item
                        name="auth_password"
                        label="密码"
                        rules={[{ required: true, message: '请输入密码' }]}
                      >
                        <Input.Password placeholder="Basic Auth 密码" />
                      </Form.Item>
                    </Col>
                  </Row>
                );
              }
              if (authType === 'bearer') {
                return (
                  <Form.Item
                    name="auth_token"
                    label="Token"
                    rules={[{ required: true, message: '请输入 Token' }]}
                  >
                    <Input.Password placeholder="Bearer Token" />
                  </Form.Item>
                );
              }
              if (authType === 'api_key') {
                return (
                  <Row gutter={16}>
                    <Col span={10}>
                      <Form.Item
                        name="auth_key"
                        label="Key"
                        rules={[{ required: true, message: '请输入 Key' }]}
                      >
                        <Input placeholder="X-API-Key" />
                      </Form.Item>
                    </Col>
                    <Col span={14}>
                      <Form.Item
                        name="auth_value"
                        label="Value"
                        rules={[{ required: true, message: '请输入 Value' }]}
                      >
                        <Input.Password placeholder="API Key Value" />
                      </Form.Item>
                    </Col>
                  </Row>
                );
              }
              return null;
            }}
          </Form.Item>
        </>
      );
    }

    if (selectedType === 'excel') {
      return (
        <Form.Item label="上传文件" required>
          <Upload
            accept=".xls,.xlsx,.csv"
            maxCount={1}
            beforeUpload={(file) => {
              setUploadedFile(file);
              return false; // Prevent auto-upload
            }}
            onRemove={() => {
              setUploadedFile(null);
            }}
            fileList={(() => {
              if (!uploadedFile) return [];
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              return [{ uid: '-1', name: uploadedFile.name, status: 'done' } as any];
            })()}
          >
            <Button icon={<FileExcelOutlined />}>选择文件 (.xls, .xlsx, .csv)</Button>
          </Upload>
          {uploadedFile && (
            <div style={{ marginTop: 8, color: '#52c41a' }}>
              <CheckCircleOutlined /> 已选择: {uploadedFile.name} ({(uploadedFile.size / 1024).toFixed(1)} KB)
            </div>
          )}
        </Form.Item>
      );
    }

    return null;
  };

  // ==================== 新建 Modal 内容 ====================

  const renderCreateStepContent = () => {
    switch (createStep) {
      case 0:
        return (
          <div style={{ padding: '20px 0' }}>
            <p style={{ marginBottom: 20, color: '#666' }}>请选择要新建的数据源类型</p>
            <Row gutter={[16, 16]}>
              {SELECTABLE_TYPES.map((type) => {
                const cfg = TYPE_CONFIG[type];
                return (
                  <Col span={8} key={type}>
                    <Card
                      hoverable
                      size="small"
                      onClick={() => handleSelectType(type)}
                      styles={{
                        body: {
                          textAlign: 'center',
                          padding: '24px 12px',
                          cursor: 'pointer',
                        },
                      }}
                    >
                      <div style={{ marginBottom: 8 }}>{cfg.icon}</div>
                      <div style={{ fontWeight: 500, fontSize: 14 }}>{cfg.label}</div>
                    </Card>
                  </Col>
                );
              })}
            </Row>
          </div>
        );

      case 1:
        return (
          <div style={{ padding: '10px 0' }}>
            {selectedType && (
              <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
                {TYPE_CONFIG[selectedType].icon}
                <span style={{ fontWeight: 600, fontSize: 16 }}>
                  {TYPE_CONFIG[selectedType].label} 连接配置
                </span>
              </div>
            )}
            <Form
              form={form}
              layout="vertical"
              preserve={false}
            >
              {renderConnectionForm()}
            </Form>
          </div>
        );

      case 2:
        return (
          <div style={{ padding: '20px 0', textAlign: 'center' }}>
            <div style={{ marginBottom: 24 }}>
              {testResult === null ? (
                <div style={{ color: '#666' }}>
                  <LinkOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} />
                  <p>点击下方按钮测试数据源连接</p>
                </div>
              ) : testResult.success ? (
                <div>
                  <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
                  <p style={{ color: '#52c41a', fontWeight: 500 }}>{testResult.message}</p>
                </div>
              ) : (
                <div>
                  <CloseCircleOutlined style={{ fontSize: 48, color: '#ff4d4f', marginBottom: 16 }} />
                  <p style={{ color: '#ff4d4f' }}>{testResult.message}</p>
                </div>
              )}
            </div>
            <Button
              type="primary"
              icon={<LinkOutlined />}
              onClick={handleTestConnection}
              loading={testing}
              style={{ minWidth: 160 }}
            >
              {testing ? '测试中...' : '测试连接'}
            </Button>
          </div>
        );

      case 3:
        return (
          <div style={{ padding: '10px 0' }}>
            <Form form={form} layout="vertical" preserve={false}>
              <Form.Item
                name="name"
                label="数据源名称"
                rules={[{ required: true, message: '请输入数据源名称' }]}
              >
                <Input placeholder="请输入数据源名称" maxLength={100} />
              </Form.Item>

              <Form.Item name="description" label="描述">
                <Input.TextArea
                  placeholder="请输入数据源描述（选填）"
                  rows={3}
                  maxLength={500}
                  showCount
                />
              </Form.Item>
            </Form>
          </div>
        );

      default:
        return null;
    }
  };

  const renderCreateModalFooter = () => {
    if (createStep === 0) {
      return (
        <Button onClick={() => setCreateModalOpen(false)}>取消</Button>
      );
    }
    if (createStep === 1) {
      return (
        <Space>
          <Button onClick={handlePrevStep}>上一步</Button>
          <Button onClick={() => setCreateModalOpen(false)}>取消</Button>
          <Button type="primary" onClick={handleNextFromConfig}>
            下一步
          </Button>
        </Space>
      );
    }
    if (createStep === 2) {
      return (
        <Space>
          <Button onClick={handlePrevStep}>上一步</Button>
          <Button onClick={() => setCreateModalOpen(false)}>取消</Button>
          <Button type="primary" onClick={handleNextToInfo} disabled={!testResult?.success}>
            下一步
          </Button>
        </Space>
      );
    }
    if (createStep === 3) {
      return (
        <Space>
          <Button onClick={handlePrevStep}>上一步</Button>
          <Button onClick={() => setCreateModalOpen(false)}>取消</Button>
          <Button type="primary" loading={createLoading} onClick={handleCreate}>
            {createLoading ? '创建中...' : '创建'}
          </Button>
        </Space>
      );
    }
    return null;
  };

  // ==================== 渲染 ====================

  const getTypeBadge = (type: DataSourceType) => {
    const cfg = TYPE_CONFIG[type];
    return (
      <Tag
        icon={cfg?.icon ? React.cloneElement(cfg.icon as React.ReactElement, { style: { fontSize: 14, color: cfg.color } }) : undefined}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}
      >
        {cfg?.label || type}
      </Tag>
    );
  };

  return (
    <div style={{ padding: 24, height: '100%' }}>
      {/* 页面头部 */}
      <Card styles={{ body: { padding: '16px 24px' } }} style={{ marginBottom: 16 }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Space size={12}>
              <DatabaseOutlined style={{ fontSize: 20 }} />
              <span style={{ fontSize: 18, fontWeight: 600 }}>数据源管理</span>
            </Space>
          </Col>
          <Col>
            <Space>
              <Button icon={<ReloadOutlined />} onClick={fetchDatasources}>
                刷新
              </Button>
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                新建数据源
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 数据源卡片网格 */}
      <Spin spinning={loading} tip="加载中...">
        {!loading && datasources.length === 0 ? (
          <Card>
            <Empty
              image={<DatabaseOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
              description="暂无数据源"
            >
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                新建数据源
              </Button>
            </Empty>
          </Card>
        ) : (
          <Row gutter={[16, 16]}>
            {datasources.map((ds) => {
              const statusCfg = STATUS_CONFIG[ds.status];
              const typeCfg = TYPE_CONFIG[ds.type];
              return (
                <Col key={ds.id} xs={24} sm={24} md={12} lg={8} xl={6}>
                  <Card
                    hoverable
                    styles={{ body: { padding: '20px' } }}
                  >
                    {/* 顶部：类型图标 + 名称 + 状态 */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        justifyContent: 'space-between',
                        marginBottom: 12,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 }}>
                        <div
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 8,
                            backgroundColor: `${typeCfg?.color || '#666'}15`,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          {typeCfg?.icon}
                        </div>
                        <div style={{ minWidth: 0 }}>
                          <div
                            style={{ fontWeight: 600, fontSize: 15, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={ds.name}
                          >
                            {ds.name}
                          </div>
                          {getTypeBadge(ds.type)}
                        </div>
                      </div>
                      <Tag
                        color={statusCfg?.color}
                        icon={statusCfg?.icon}
                        style={{ flexShrink: 0, marginLeft: 8 }}
                      >
                        {statusCfg?.text || ds.status}
                      </Tag>
                    </div>

                    {/* 描述 */}
                    <div
                      style={{
                        color: '#666',
                        fontSize: 13,
                        marginBottom: 12,
                        minHeight: 40,
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                      }}
                    >
                      {ds.description || '暂无描述'}
                    </div>

                    {/* 创建时间 */}
                    <div style={{ color: '#999', fontSize: 12, marginBottom: 16 }}>
                      创建时间: {dayjs(ds.created_at).format('YYYY-MM-DD HH:mm')}
                    </div>

                    {/* 操作按钮 */}
                    <div
                      style={{
                        borderTop: '1px solid #f0f0f0',
                        paddingTop: 12,
                        display: 'flex',
                        justifyContent: 'space-between',
                      }}
                    >
                      <Button
                        type="link"
                        size="small"
                        icon={<EditOutlined />}
                        onClick={() => handleEdit(ds)}
                      >
                        编辑
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        icon={<LinkOutlined />}
                        onClick={() => handleTestExisting(ds)}
                      >
                        测试
                      </Button>
                      <Button
                        type="link"
                        size="small"
                        icon={<SyncOutlined />}
                        onClick={() => handleSyncMetadata(ds)}
                      >
                        同步
                      </Button>
                      <Popconfirm
                        title="确认删除"
                        description={`确定要删除数据源"${ds.name}"吗？`}
                        onConfirm={() => handleDelete(ds.id)}
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                          删除
                        </Button>
                      </Popconfirm>
                    </div>
                  </Card>
                </Col>
              );
            })}
          </Row>
        )}
      </Spin>

      {/* 新建数据源 Modal */}
      <Modal
        title="新建数据源"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={renderCreateModalFooter()}
        width={680}
        destroyOnClose
        maskClosable={false}
      >
        <Steps
          current={createStep}
          items={stepsItems}
          size="small"
          style={{ marginBottom: 24 }}
        />
        {renderCreateStepContent()}
      </Modal>

      {/* 编辑数据源 Modal */}
      <Modal
        title="编辑数据源"
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        footer={null}
        destroyOnClose
        width={480}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEditSubmit}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="name"
            label="数据源名称"
            rules={[{ required: true, message: '请输入数据源名称' }]}
          >
            <Input placeholder="请输入数据源名称" maxLength={100} />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea
              placeholder="请输入数据源描述（选填）"
              rows={3}
              maxLength={500}
              showCount
            />
          </Form.Item>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setEditModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={editLoading}>
                {editLoading ? '保存中...' : '保存'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DatasourcePage;
