/**
 * DataVision 看板管理页
 *
 * 功能：
 * - 看板列表展示（表格 + 分页 + 标题搜索）
 * - 新建看板（Modal 表单）
 * - 编辑 / 删除 / 发布操作
 * - 点击行跳转到看板设计器
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
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
} from 'antd';
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  SendOutlined,
  ReloadOutlined,
  DashboardOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { TablePaginationConfig } from 'antd/es/table';
import dayjs from 'dayjs';
import api from '@/services/api';
import type { APIResponse, PaginatedData, Dashboard } from '@/types';

// ==================== 常量 ====================

const CATEGORY_OPTIONS = [
  { label: '运营分析', value: '运营分析' },
  { label: '销售看板', value: '销售看板' },
  { label: '财务分析', value: '财务分析' },
  { label: '用户分析', value: '用户分析' },
  { label: '产品分析', value: '产品分析' },
  { label: '实时监控', value: '实时监控' },
  { label: '其他', value: '其他' },
];

const THEME_OPTIONS = [
  { label: '默认主题', value: 'default' },
  { label: '暗色主题', value: 'dark' },
  { label: '亮色主题', value: 'light' },
  { label: '蓝色科技', value: 'blue' },
  { label: '绿色清新', value: 'green' },
];

// ==================== 表单类型 ====================

interface CreateFormValues {
  title: string;
  description?: string;
  category?: string;
  theme?: string;
}

// ==================== 组件 ====================

const DashboardPage: React.FC = () => {
  const navigate = useNavigate();

  // ---------- 列表状态 ----------
  const [loading, setLoading] = useState(false);
  const [dashboards, setDashboards] = useState<Dashboard[]>([]);
  const [pagination, setPagination] = useState({ page: 1, pageSize: 10, total: 0 });
  const [searchText, setSearchText] = useState('');

  // ---------- 新建 / 编辑 Modal ----------
  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [form] = Form.useForm<CreateFormValues>();

  // ==================== 数据获取 ====================

  const fetchDashboards = useCallback(
    async (page = 1, pageSize = 10, title = '') => {
      setLoading(true);
      try {
        const params: Record<string, unknown> = {
          page,
          page_size: pageSize,
        };
        if (title.trim()) {
          params.title = title.trim();
        }

        const res = await api.get<APIResponse<PaginatedData<Dashboard>>>('/dashboards', { params });
        const { code, message: msg, data } = res.data;

        if (code !== 0 && code !== 200) {
          message.error(msg || '获取看板列表失败');
          return;
        }

        setDashboards(data.items);
        setPagination({ page: data.page, pageSize: data.page_size, total: data.total });
      } catch (err: unknown) {
        const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
        message.error(errorMessage);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    fetchDashboards();
  }, [fetchDashboards]);

  // ==================== 操作处理 ====================

  /** 新建看板 */
  const handleCreate = async (values: CreateFormValues) => {
    setModalLoading(true);
    try {
      const res = await api.post<APIResponse<Dashboard>>('/dashboards', {
        title: values.title,
        description: values.description || '',
        category: values.category || null,
        theme: values.theme || 'default',
        width: 1200,
        height: 800,
        is_published: false,
        refresh_interval: 0,
        tags: [],
        components: [],
      });

      const { code, message: msg, data } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '创建失败');
        return;
      }

      message.success('看板创建成功！');
      setModalOpen(false);
      form.resetFields();

      // 刷新列表
      fetchDashboards(pagination.page, pagination.pageSize, searchText);

      // 可选：直接跳转到新的看板设计器
      if (data?.id) {
        navigate(`/dashboards/${data.id}`);
      }
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    } finally {
      setModalLoading(false);
    }
  };

  /** 删除看板 */
  const handleDelete = async (id: string) => {
    try {
      const res = await api.delete<APIResponse<null>>(`/dashboards/${id}`);
      const { code, message: msg } = res.data;

      if (code !== 0 && code !== 200) {
        message.error(msg || '删除失败');
        return;
      }

      message.success('看板已删除');
      // 如果当前页删除后没有数据了，回到上一页
      const newPage = dashboards.length === 1 && pagination.page > 1
        ? pagination.page - 1
        : pagination.page;
      fetchDashboards(newPage, pagination.pageSize, searchText);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    }
  };

  /** 发布 / 取消发布 */
  const handleTogglePublish = async (dashboard: Dashboard) => {
    try {
      const newPublished = !dashboard.is_published;
      const res = await api.put<APIResponse<Dashboard>>(`/dashboards/${dashboard.id}`, {
        ...dashboard,
        is_published: newPublished,
      });

      const { code, message: msg } = res.data;
      if (code !== 0 && code !== 200) {
        message.error(msg || '操作失败');
        return;
      }

      message.success(newPublished ? '看板已发布' : '已取消发布');
      fetchDashboards(pagination.page, pagination.pageSize, searchText);
    } catch (err: unknown) {
      const errorMessage = (err as { message?: string })?.message || '网络异常，请稍后重试';
      message.error(errorMessage);
    }
  };

  /** 搜索 */
  const handleSearch = (value: string) => {
    setSearchText(value);
    fetchDashboards(1, pagination.pageSize, value);
  };

  /** 分页变化 */
  const handleTableChange = (pag: TablePaginationConfig) => {
    fetchDashboards(pag.current || 1, pag.pageSize || 10, searchText);
  };

  // ==================== 表格列定义 ====================

  const columns: ColumnsType<Dashboard> = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      width: 220,
      ellipsis: true,
      render: (text: string, record: Dashboard) => (
        <a
          onClick={() => navigate(`/dashboards/${record.id}`)}
          style={{ fontWeight: 500 }}
        >
          {text}
        </a>
      ),
    },
    {
      title: '分类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      render: (text: string | null) => text || <span style={{ color: '#999' }}>-</span>,
    },
    {
      title: '发布状态',
      dataIndex: 'is_published',
      key: 'is_published',
      width: 110,
      render: (published: boolean) =>
        published ? (
          <Tag color="green">已发布</Tag>
        ) : (
          <Tag color="default">未发布</Tag>
        ),
    },
    {
      title: '组件数量',
      dataIndex: 'components',
      key: 'component_count',
      width: 100,
      align: 'center',
      render: (components: Dashboard['components']) => components?.length ?? 0,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 180,
      render: (text: string) => dayjs(text).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作',
      key: 'actions',
      width: 260,
      fixed: 'right',
      render: (_: unknown, record: Dashboard) => (
        <Space size="small">
          {/* 编辑 - 跳转到设计器 */}
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => navigate(`/dashboards/${record.id}`)}
          >
            编辑
          </Button>

          {/* 发布 / 取消发布 */}
          <Popconfirm
            title={record.is_published ? '确认取消发布？' : '确认发布？'}
            description={
              record.is_published
                ? '取消发布后，分享链接将失效。'
                : '发布后看板将可通过链接访问。'
            }
            onConfirm={() => handleTogglePublish(record)}
            okText="确认"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              icon={<SendOutlined />}
            >
              {record.is_published ? '取消发布' : '发布'}
            </Button>
          </Popconfirm>

          {/* 删除 */}
          <Popconfirm
            title="确认删除"
            description={`确定要删除看板"${record.title}"吗？此操作不可恢复。`}
            onConfirm={() => handleDelete(record.id)}
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

  // ==================== 渲染 ====================

  return (
    <div style={{ padding: 24, height: '100%' }}>
      {/* 页面头部 */}
      <Card
        styles={{ body: { padding: '16px 24px' } }}
        style={{ marginBottom: 16 }}
      >
        <Row justify="space-between" align="middle">
          <Col>
            <Space size={12}>
              <DashboardOutlined style={{ fontSize: 20 }} />
              <span style={{ fontSize: 18, fontWeight: 600 }}>看板管理</span>
            </Space>
          </Col>
          <Col>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={() => fetchDashboards(pagination.page, pagination.pageSize, searchText)}
              >
                刷新
              </Button>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                onClick={() => {
                  form.resetFields();
                  setModalOpen(true);
                }}
              >
                新建看板
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 搜索栏 */}
      <Card
        styles={{ body: { padding: '12px 24px' } }}
        style={{ marginBottom: 16 }}
      >
        <Input.Search
          placeholder="搜索看板标题..."
          allowClear
          onSearch={handleSearch}
          style={{ width: 320 }}
          prefix={<SearchOutlined style={{ color: '#bfbfbf' }} />}
        />
      </Card>

      {/* 看板表格 */}
      <Card styles={{ body: { padding: 0 } }}>
        <Table<Dashboard>
          rowKey="id"
          columns={columns}
          dataSource={dashboards}
          loading={loading}
          pagination={{
            current: pagination.page,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showQuickJumper: true,
            pageSizeOptions: ['10', '20', '50'],
            showTotal: (total: number) => `共 ${total} 个看板`,
          }}
          onChange={handleTableChange}
          scroll={{ x: 990 }}
          locale={{
            emptyText: (
              <div style={{ padding: '60px 0' }}>
                <DashboardOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                <p style={{ marginTop: 16, color: '#999' }}>暂无看板</p>
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => {
                    form.resetFields();
                    setModalOpen(true);
                  }}
                >
                  新建看板
                </Button>
              </div>
            ),
          }}
        />
      </Card>

      {/* 新建看板 Modal */}
      <Modal
        title="新建看板"
        open={modalOpen}
        onCancel={() => {
          setModalOpen(false);
          form.resetFields();
        }}
        footer={null}
        destroyOnClose
        width={560}
      >
        <Form<CreateFormValues>
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ theme: 'default' }}
          style={{ marginTop: 16 }}
        >
          <Form.Item
            name="title"
            label="看板标题"
            rules={[{ required: true, message: '请输入看板标题' }]}
          >
            <Input placeholder="请输入看板标题" maxLength={100} />
          </Form.Item>

          <Form.Item name="description" label="看板描述">
            <Input.TextArea
              placeholder="请输入看板描述（选填）"
              rows={3}
              maxLength={500}
              showCount
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="category" label="分类">
                <Select
                  placeholder="请选择分类"
                  allowClear
                  options={CATEGORY_OPTIONS}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="theme" label="主题">
                <Select options={THEME_OPTIONS} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item style={{ marginBottom: 0, textAlign: 'right' }}>
            <Space>
              <Button
                onClick={() => {
                  setModalOpen(false);
                  form.resetFields();
                }}
              >
                取消
              </Button>
              <Button type="primary" htmlType="submit" loading={modalLoading}>
                {modalLoading ? '创建中...' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default DashboardPage;
