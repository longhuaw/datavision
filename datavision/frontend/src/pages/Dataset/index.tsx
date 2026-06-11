/**
 * DataVision 数据集管理页
 *
 * 功能：
 * - 数据集表格展示（名称、数据源、状态、行数、缓存TTL、更新时间、操作）
 * - 新建数据集 Modal（选择数据源 → SQL查询/可视化模式 → 命名+描述+缓存TTL）
 * - 行操作：预览（Drawer，前100行）、编辑、删除、切换状态
 * - 加载态 / 空状态
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Table,
  Button,
  Modal,
  Drawer,
  Form,
  Input,
  InputNumber,
  Select,
  Tag,
  Space,
  message,
  Spin,
  Empty,
  Popconfirm,
  Switch,
  Tabs,
  Tooltip,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  PlayCircleOutlined,
  DatabaseOutlined,
  TableOutlined,
  CodeOutlined,
  BarChartOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import api from '@/services/api';
import type { APIResponse, Dataset, DatasetPreview, DataSource } from '@/types';

// ==================== 状态配置 ====================

const STATUS_CONFIG: Record<
  string,
  { color: string; text: string; icon: React.ReactNode }
> = {
  published: {
    color: 'green',
    text: '已发布',
    icon: <CheckCircleOutlined />,
  },
  draft: {
    color: 'blue',
    text: '草稿',
    icon: <EditOutlined />,
  },
  archived: {
    color: 'default',
    text: '已归档',
    icon: <PauseCircleOutlined />,
  },
};

// ==================== 表单类型 ====================

interface CreateFormValues {
  name: string;
  description: string;
  datasource_id: string;
  sql_text: string;
  cache_ttl: number;
}

interface EditFormValues {
  name: string;
  description: string;
  datasource_id: string;
  sql_text: string;
}

// ==================== 组件 ====================

const DatasetPage: React.FC = () => {
  // ---------- 列表状态 ----------
  const [loading, setLoading] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);

  // ---------- 数据源列表（用于下拉选择） ----------
  const [datasources, setDatasources] = useState<DataSource[]>([]);

  // ---------- 新建 Modal 状态 ----------
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm<CreateFormValues>();
  const [queryMode, setQueryMode] = useState<'sql' | 'visual'>('sql');

  // ---------- 编辑 Modal 状态 ----------
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editLoading, setEditLoading] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Dataset | null>(null);
  const [editForm] = Form.useForm<EditFormValues>();

  // ---------- 预览 Drawer 状态 ----------
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<DatasetPreview | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState('');

  // ==================== 数据获取 ====================

  const fetchDatasets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<APIResponse<Dataset[]>>('/datasets');
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('获取数据集列表失败');
        return;
      }
      setDatasets(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDatasources = useCallback(async () => {
    try {
      const res = await api.get<APIResponse<DataSource[]>>('/datasources');
      const { code, data } = res.data;
      if (code === 0 || code === 200) {
        setDatasources(Array.isArray(data) ? data : []);
      }
    } catch {
      // 静默处理，数据源下拉列表获取失败不影响主流程
    }
  }, []);

  useEffect(() => {
    fetchDatasets();
    fetchDatasources();
  }, [fetchDatasets, fetchDatasources]);

  // ==================== 新建数据集 ====================

  const openCreateModal = () => {
    createForm.resetFields();
    createForm.setFieldsValue({
      cache_ttl: 3600,
      sql_text: '',
    });
    setQueryMode('sql');
    setCreateModalOpen(true);
  };

  const handleCreate = async () => {
    try {
      const values = await createForm.validateFields();
      setCreateLoading(true);

      const res = await api.post<APIResponse<Dataset>>('/datasets', {
        name: values.name,
        description: values.description || '',
        datasource_id: values.datasource_id,
        sql_text: values.sql_text || '',
        cache_ttl: values.cache_ttl ?? 3600,
      });

      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('创建数据集失败');
        return;
      }

      message.success('数据集创建成功！');
      setCreateModalOpen(false);
      fetchDatasets();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) {
        // 表单验证错误，antd 已展示
        return;
      }
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setCreateLoading(false);
    }
  };

  // ==================== 编辑数据集 ====================

  const handleEdit = (record: Dataset) => {
    setEditingRecord(record);
    editForm.setFieldsValue({
      name: record.name,
      description: record.description,
      datasource_id: record.datasource_id,
      sql_text: record.sql_text,
    });
    setEditModalOpen(true);
  };

  const handleEditSubmit = async () => {
    try {
      const values = await editForm.validateFields();
      if (!editingRecord) return;
      setEditLoading(true);

      const res = await api.put<APIResponse<Dataset>>(`/datasets/${editingRecord.id}`, {
        name: values.name,
        description: values.description || '',
        datasource_id: values.datasource_id,
        sql_text: values.sql_text,
      });

      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('更新失败');
        return;
      }
      message.success('数据集更新成功！');
      setEditModalOpen(false);
      fetchDatasets();
    } catch (err: unknown) {
      if ((err as { errorFields?: unknown[] })?.errorFields) return;
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setEditLoading(false);
    }
  };

  // ==================== 删除 ====================

  const handleDelete = async (id: string) => {
    try {
      const res = await api.delete<APIResponse<null>>(`/datasets/${id}`);
      const { code } = res.data;
      if (code !== 0 && code !== 200) {
        message.error('删除失败');
        return;
      }
      message.success('数据集已删除');
      fetchDatasets();
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    }
  };

  // ==================== 切换状态 ====================

  const handleToggleStatus = async (record: Dataset) => {
    const nextStatus = record.status === 'published' ? 'archived' : 'published';
    message.loading({ content: '正在切换状态...', key: 'toggle-status' });
    try {
      const res = await api.put<APIResponse<Dataset>>(`/datasets/${record.id}`, {
        status: nextStatus,
      });
      const { code } = res.data;
      if (code === 0 || code === 200) {
        message.success({ content: `状态已切换为"${STATUS_CONFIG[nextStatus]?.text || nextStatus}"`, key: 'toggle-status' });
        fetchDatasets();
      } else {
        message.error({
          content: (res.data as { message?: string })?.message || '切换状态失败',
          key: 'toggle-status',
        });
      }
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error({ content: errorMessage, key: 'toggle-status' });
    }
  };

  // ==================== 预览 ====================

  const handlePreview = async (record: Dataset) => {
    setPreviewOpen(true);
    setPreviewTitle(record.name);
    setPreviewLoading(true);
    setPreviewError(null);
    setPreviewData(null);

    try {
      const res = await api.get<APIResponse<DatasetPreview>>(`/datasets/${record.id}/preview`);
      const { code, data } = res.data;
      if (code !== 0 && code !== 200) {
        setPreviewError('获取预览数据失败');
        return;
      }
      setPreviewData(data ?? null);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      setPreviewError(errorMessage);
    } finally {
      setPreviewLoading(false);
    }
  };

  // ==================== 表格列定义 ====================

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      ellipsis: true,
      render: (text: string, record: Dataset) => (
        <Tooltip title={record.description || text}>
          <span style={{ fontWeight: 500 }}>{text}</span>
          {record.description && (
            <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>{record.description}</div>
          )}
        </Tooltip>
      ),
    },
    {
      title: '数据源',
      dataIndex: 'datasource_name',
      key: 'datasource_name',
      width: 150,
      render: (text: string) => (
        <Space size={4}>
          <DatabaseOutlined style={{ color: '#1677ff' }} />
          <span>{text || '-'}</span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: string) => {
        const cfg = STATUS_CONFIG[status] || { color: 'default', text: status, icon: null };
        return (
          <Tag color={cfg.color} icon={cfg.icon}>
            {cfg.text}
          </Tag>
        );
      },
    },
    {
      title: '行数',
      dataIndex: 'row_count',
      key: 'row_count',
      width: 100,
      align: 'right' as const,
      render: (val: number | null) => {
        if (val === null || val === undefined) return <span style={{ color: '#999' }}>-</span>;
        return val.toLocaleString();
      },
    },
    {
      title: '缓存 TTL',
      dataIndex: 'cache_ttl',
      key: 'cache_ttl',
      width: 110,
      align: 'center' as const,
      render: (val: number) => {
        if (!val) return <span style={{ color: '#999' }}>-</span>;
        if (val >= 3600) return `${(val / 3600).toFixed(1)} 小时`;
        if (val >= 60) return `${(val / 60).toFixed(0)} 分钟`;
        return `${val} 秒`;
      },
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
      render: (val: string) => (val ? dayjs(val).format('YYYY-MM-DD HH:mm:ss') : '-'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 280,
      fixed: 'right' as const,
      render: (_: unknown, record: Dataset) => (
        <Space size="small">
          <Tooltip title="预览数据（前100行）">
            <Button
              type="link"
              size="small"
              icon={<EyeOutlined />}
              onClick={() => handlePreview(record)}
            >
              预览
            </Button>
          </Tooltip>
          <Tooltip title="编辑数据集">
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => handleEdit(record)}
            >
              编辑
            </Button>
          </Tooltip>
          <Popconfirm
            title="确认删除"
            description={`确定要删除数据集"${record.name}"吗？此操作不可恢复。`}
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="删除">
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Tooltip>
          </Popconfirm>
          <Tooltip title={record.status === 'published' ? '归档' : '发布'}>
            <Button
              type="link"
              size="small"
              icon={record.status === 'published' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
              onClick={() => handleToggleStatus(record)}
            >
              {record.status === 'published' ? '归档' : '发布'}
            </Button>
          </Tooltip>
        </Space>
      ),
    },
  ];

  // ==================== 渲染预览 Drawer ====================

  const renderPreviewContent = () => {
    if (previewLoading) {
      return (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <Spin size="large" tip="正在加载预览数据..." />
        </div>
      );
    }

    if (previewError) {
      return (
        <div style={{ textAlign: 'center', padding: '60px 0' }}>
          <ExclamationCircleOutlined style={{ fontSize: 48, color: '#ff4d4f', marginBottom: 16 }} />
          <p style={{ color: '#ff4d4f' }}>{previewError}</p>
        </div>
      );
    }

    if (!previewData || !previewData.columns || previewData.columns.length === 0) {
      return (
        <Empty
          description="暂无预览数据"
          image={<TableOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />}
        />
      );
    }

    const { columns: cols, rows, total_rows, execution_time_ms } = previewData;

    const dataSource = rows.map((row, idx) => {
      const record: Record<string, unknown> = { _key: idx };
      cols.forEach((col) => {
        const val = row[col];
        record[col] = val !== null && val !== undefined ? String(val) : '';
      });
      return record;
    });

    const tableColumns = cols.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      width: 150,
      ellipsis: true,
      render: (val: string) => (
        <Tooltip title={val}>
          <span>{val || <span style={{ color: '#ccc' }}>NULL</span>}</span>
        </Tooltip>
      ),
    }));

    return (
      <div>
        <div style={{ marginBottom: 12, color: '#666', fontSize: 13 }}>
          共 {total_rows} 行（显示前 {rows.length} 行），查询耗时 {execution_time_ms}ms
        </div>
        <Table
          columns={tableColumns}
          dataSource={dataSource}
          rowKey="_key"
          size="small"
          scroll={{ x: cols.length * 150, y: 'calc(100vh - 280px)' }}
          pagination={false}
        />
      </div>
    );
  };

  // ==================== 渲染 ====================

  return (
    <div style={{ padding: 24, height: '100%' }}>
      {/* 页面头部 */}
      <div
        style={{
          marginBottom: 16,
          padding: '16px 24px',
          background: '#fff',
          borderRadius: 8,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Space size={12}>
          <TableOutlined style={{ fontSize: 20 }} />
          <span style={{ fontSize: 18, fontWeight: 600 }}>数据集管理</span>
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={fetchDatasets}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
            新建数据集
          </Button>
        </Space>
      </div>

      {/* 表格区域 */}
      <Spin spinning={loading} tip="加载中...">
        {!loading && datasets.length === 0 ? (
          <div style={{ background: '#fff', borderRadius: 8, padding: 60 }}>
            <Empty
              image={<TableOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
              description="暂无数据集"
            >
              <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
                新建数据集
              </Button>
            </Empty>
          </div>
        ) : (
          <div style={{ background: '#fff', borderRadius: 8 }}>
            <Table
              columns={columns}
              dataSource={datasets}
              rowKey="id"
              scroll={{ x: 1200 }}
              size="middle"
              pagination={{
                showSizeChanger: true,
                showQuickJumper: true,
                showTotal: (total) => `共 ${total} 条`,
                pageSizeOptions: ['10', '20', '50', '100'],
                defaultPageSize: 20,
              }}
            />
          </div>
        )}
      </Spin>

      {/* 新建数据集 Modal */}
      <Modal
        title="新建数据集"
        open={createModalOpen}
        onCancel={() => setCreateModalOpen(false)}
        footer={null}
        width={720}
        destroyOnClose
        maskClosable={false}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
          preserve={false}
          initialValues={{ cache_ttl: 3600 }}
          style={{ marginTop: 16 }}
        >
          {/* 选择数据源 */}
          <Form.Item
            name="datasource_id"
            label="数据源"
            rules={[{ required: true, message: '请选择数据源' }]}
          >
            <Select
              placeholder="请选择数据源"
              showSearch
              optionFilterProp="label"
              options={datasources.map((ds) => ({
                label: ds.name,
                value: ds.id,
              }))}
              notFoundContent={
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无可用数据源，请先创建数据源"
                  style={{ padding: '16px 0' }}
                />
              }
            />
          </Form.Item>

          {/* 查询构建 - Tab 切换 SQL / 可视化 */}
          <Form.Item label="查询定义">
            <Tabs
              activeKey={queryMode}
              onChange={(key) => setQueryMode(key as 'sql' | 'visual')}
              items={[
                {
                  key: 'sql',
                  label: (
                    <span>
                      <CodeOutlined /> SQL 模式
                    </span>
                  ),
                  children: (
                    <Form.Item
                      name="sql_text"
                      noStyle
                      rules={[{ required: true, message: '请输入 SQL 查询语句' }]}
                    >
                      <Input.TextArea
                        placeholder="SELECT * FROM table_name WHERE ..."
                        rows={8}
                        style={{
                          fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                          minHeight: 200,
                          fontSize: 13,
                        }}
                        spellCheck={false}
                      />
                    </Form.Item>
                  ),
                },
                {
                  key: 'visual',
                  label: (
                    <span>
                      <BarChartOutlined /> 可视化模式
                    </span>
                  ),
                  children: (
                    <div
                      style={{
                        textAlign: 'center',
                        padding: '40px 20px',
                        color: '#999',
                        border: '1px dashed #d9d9d9',
                        borderRadius: 6,
                        minHeight: 200,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <BarChartOutlined style={{ fontSize: 36, color: '#d9d9d9', marginBottom: 12 }} />
                      <p>可视化查询构建器将在后续版本中提供</p>
                      <p style={{ fontSize: 12, color: '#bbb' }}>
                        请先使用 SQL 模式定义查询
                      </p>
                    </div>
                  ),
                },
              ]}
            />
          </Form.Item>

          {/* 基本信息 */}
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[
              { required: true, message: '请输入数据集名称' },
              { max: 100, message: '名称不超过100个字符' },
            ]}
          >
            <Input placeholder="请输入数据集名称" maxLength={100} />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea
              placeholder="请输入数据集描述（选填）"
              rows={2}
              maxLength={500}
              showCount
            />
          </Form.Item>

          <Form.Item
            name="cache_ttl"
            label="缓存 TTL（秒）"
            rules={[{ type: 'number', min: 0, message: '缓存 TTL 不能为负数' }]}
            extra="设置为 0 表示不缓存，默认 3600 秒（1小时）"
          >
            <InputNumber
              min={0}
              max={86400}
              style={{ width: '100%' }}
              placeholder="3600"
              addonAfter="秒"
            />
          </Form.Item>

          {/* 提交 */}
          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button onClick={() => setCreateModalOpen(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={createLoading}>
                {createLoading ? '创建中...' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑数据集 Modal */}
      <Modal
        title="编辑数据集"
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        footer={null}
        destroyOnClose
        width={720}
        maskClosable={false}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleEditSubmit}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="datasource_id"
            label="数据源"
            rules={[{ required: true, message: '请选择数据源' }]}
          >
            <Select
              placeholder="请选择数据源"
              showSearch
              optionFilterProp="label"
              options={datasources.map((ds) => ({
                label: ds.name,
                value: ds.id,
              }))}
              notFoundContent={
                <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无可用数据源"
                  style={{ padding: '16px 0' }}
                />
              }
            />
          </Form.Item>

          <Form.Item
            name="sql_text"
            label="SQL 查询"
            rules={[{ required: true, message: '请输入 SQL 查询语句' }]}
          >
            <Input.TextArea
              placeholder="SELECT * FROM table_name WHERE ..."
              rows={8}
              style={{
                fontFamily: 'Consolas, Monaco, "Courier New", monospace',
                minHeight: 200,
                fontSize: 13,
              }}
              spellCheck={false}
            />
          </Form.Item>

          <Form.Item
            name="name"
            label="数据集名称"
            rules={[
              { required: true, message: '请输入数据集名称' },
              { max: 100, message: '名称不超过100个字符' },
            ]}
          >
            <Input placeholder="请输入数据集名称" maxLength={100} />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea
              placeholder="请输入数据集描述（选填）"
              rows={2}
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

      {/* 预览 Drawer */}
      <Drawer
        title={
          <Space>
            <EyeOutlined />
            <span>预览: {previewTitle}</span>
          </Space>
        }
        open={previewOpen}
        onClose={() => {
          setPreviewOpen(false);
          setPreviewData(null);
          setPreviewError(null);
        }}
        width={Math.min(window.innerWidth * 0.85, 1200)}
        destroyOnClose
      >
        {renderPreviewContent()}
      </Drawer>
    </div>
  );
};

export default DatasetPage;
