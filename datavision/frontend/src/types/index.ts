// ==================== 通用类型 ====================
export interface APIResponse<T = unknown> {
  code: number;
  message: string;
  data: T;
}

export interface PaginatedData<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

// ==================== 用户相关 ====================
export interface User {
  id: string;
  username: string;
  email: string | null;
  nickname: string | null;
  avatar: string | null;
  role: 'admin' | 'editor' | 'viewer' | 'user';
  status: 'active' | 'disabled' | 'pending';
  last_login_at: string | null;
  created_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// ==================== 数据源相关 ====================
export type DataSourceType = 'mysql' | 'postgresql' | 'clickhouse' | 'sqlite' | 'mssql' | 'api' | 'excel';

export interface DataSource {
  id: string;
  name: string;
  description: string;
  type: DataSourceType;
  config: Record<string, unknown>;
  status: 'active' | 'error' | 'disabled';
  version: number;
  created_by: string;
  tags: string[];
  icon: string | null;
  created_at: string;
  updated_at: string;
}

export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  primary_key: boolean;
  comment: string;
}

export interface TableInfo {
  table_name: string;
  columns: ColumnInfo[];
}

// ==================== 数据集相关 ====================
export interface Dataset {
  id: string;
  name: string;
  description: string;
  datasource_id: string;
  datasource_name: string;
  sql_text: string;
  schema_info: DatasetColumn[] | null;
  config: Record<string, unknown> | null;
  cache_ttl: number;
  row_count: number | null;
  status: 'draft' | 'published' | 'archived';
  category: string | null;
  tags: string[];
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface DatasetColumn {
  id?: string;
  column_name: string;
  alias?: string;
  data_type: string;
  is_virtual?: boolean;
  virtual_expr?: string;
  is_dimension?: boolean;
  is_metric?: boolean;
  default_aggregation?: string;
  format_config?: Record<string, unknown>;
  semantic_type?: string;
  sort_order?: number;
}

export interface DatasetPreview {
  columns: string[];
  rows: Record<string, unknown>[];
  total_rows: number;
  execution_time_ms: number;
}

// ==================== 图表相关 ====================
export type ChartType =
  | 'line' | 'bar' | 'pie' | 'scatter' | 'heatmap'
  | 'funnel' | 'radar' | 'sankey' | 'map' | 'table'
  | 'gauge' | 'treemap' | 'wordcloud' | 'area' | 'card';

export interface ChartDimension {
  field: string;
  alias?: string;
  order: number;
}

export interface ChartMetric {
  field: string;
  aggregation: 'sum' | 'count' | 'avg' | 'max' | 'min' | 'distinct';
  alias?: string;
  order: number;
}

export interface ChartFilter {
  field: string;
  operator: '=' | '!=' | '>' | '<' | '>=' | '<=' | 'IN' | 'LIKE' | 'BETWEEN' | 'IS NULL' | 'IS NOT NULL';
  value: string | number | string[];
}

export interface ChartConfig {
  dimensions: ChartDimension[];
  metrics: ChartMetric[];
  filters?: ChartFilter[];
  order_by?: { field: string; direction: 'asc' | 'desc' }[];
  limit?: number;
}

export interface ChartStyleConfig {
  title?: { text?: string; show?: boolean; fontSize?: number };
  colors?: string[];
  legend?: { show?: boolean; position?: string };
  tooltip?: { show?: boolean };
  animation?: { enabled?: boolean; duration?: number };
  theme?: string;
}

export interface Chart {
  id: string;
  name: string;
  description: string;
  chart_type: ChartType;
  dataset_id: string;
  dataset_name: string;
  config: ChartConfig | null;
  style_config: ChartStyleConfig | null;
  query_config: { refresh_interval?: number; cache_enabled?: boolean; max_rows?: number } | null;
  nl_prompt: string | null;
  generated_sql: string | null;
  nl_confidence: number | null;
  thumbnail_url: string | null;
  version: number;
  is_template: boolean;
  category: string | null;
  usage_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ChartData {
  chart_id: string;
  data: {
    columns: string[];
    rows: Record<string, unknown>[];
  };
  cached: boolean;
  execution_time_ms: number;
}

export interface NLQueryRequest {
  prompt: string;
  dataset_id?: string;
  chart_type?: string;
}

export interface NLQueryResponse {
  prompt: string;
  generated_sql: string;
  chart_type: string;
  confidence: number;
  suggested_chart_type?: string;
}

// ==================== 看板相关 ====================
export interface DashboardComponent {
  id: string;
  chart_id: string;
  chart_name: string;
  chart_type: string;
  position: { x: number; y: number; w: number; h: number };
  z_index: number;
  config: Record<string, unknown> | null;
  sort_order: number;
}

export interface Dashboard {
  id: string;
  title: string;
  description: string;
  theme: string;
  width: number;
  height: number;
  background: string | null;
  is_published: boolean;
  publish_url: string | null;
  password_protected: boolean;
  refresh_interval: number;
  category: string | null;
  tags: string[];
  components: DashboardComponent[];
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ShareRecord {
  id: string;
  share_type: 'link' | 'embed';
  token: string;
  expires_at: string | null;
  access_count: number;
  last_accessed_at: string | null;
}

// ==================== 布局相关 ====================
export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
  static?: boolean;
}

// ==================== AI 相关 ====================
export interface AIAnalysisResult {
  summary: string;
  trends: { field: string; direction: 'up' | 'down' | 'stable'; strength: number }[];
  anomalies: { index: number; value: number; deviation_score: number }[];
  insights: string[];
}
