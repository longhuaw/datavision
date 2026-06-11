import React, { useMemo, useCallback } from 'react';
import { Table, Empty, Button, Space, Skeleton, Typography } from 'antd';
import { DownloadOutlined, InboxOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

export interface DataPreviewProps {
  /** Column names displayed as table headers */
  columns: string[];
  /** Row data objects */
  rows: Record<string, unknown>[];
  /** Whether data is being fetched */
  loading?: boolean;
  /** Total number of rows in the dataset (may exceed visible rows) */
  totalRows?: number;
  /** Query execution time in milliseconds */
  executionTimeMs?: number;
  /** Maximum table body height in pixels. Defaults to 400. */
  maxHeight?: number;
}

interface DataRow {
  _key: number;
  [key: string]: unknown;
}

/**
 * Escape a CSV field value — wraps in quotes and escapes inner quotes.
 */
function escapeCSVField(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

/**
 * Export visible rows + columns as a UTF-8 CSV file with BOM.
 */
function exportCSV(columns: string[], rows: Record<string, unknown>[]): void {
  const header = columns.map(escapeCSVField).join(',');
  const body = rows
    .map((row) =>
      columns.map((col) => escapeCSVField(String(row[col] ?? ''))).join(','),
    )
    .join('\n');

  const bom = '﻿';
  const blob = new Blob([bom + header + '\n' + body], {
    type: 'text/csv;charset=utf-8;',
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `data_export_${Date.now()}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

/**
 * Generate Skeleton rows that match the column count.
 */
function buildSkeletonRows(
  columnCount: number,
  rows: number = 8,
): DataRow[] {
  return Array.from({ length: rows }, (_, i) => {
    const row: DataRow = { _key: i };
    for (let c = 0; c < columnCount; c++) {
      row[`_sk_${c}`] = '';
    }
    return row;
  });
}

const LOADING_ROW_COUNT = 8;
const DEFAULT_MAX_HEIGHT = 400;
const DEFAULT_COL_WIDTH = 150;

const DataPreview: React.FC<DataPreviewProps> = ({
  columns,
  rows,
  loading = false,
  totalRows,
  executionTimeMs,
  maxHeight = DEFAULT_MAX_HEIGHT,
}) => {
  const handleExport = useCallback(() => {
    exportCSV(columns, rows);
  }, [columns, rows]);

  const tableColumns: ColumnsType<DataRow> = useMemo(() => {
    if (loading) {
      // During loading we may not have real columns — render skeleton placeholders
      return Array.from({ length: columns.length || 5 }, (_, i) => ({
        title: columns[i] ?? `_col_${i}`,
        dataIndex: `_sk_${i}`,
        key: `_sk_${i}`,
        ellipsis: true,
        width: DEFAULT_COL_WIDTH,
        render: () => (
          <Skeleton.Input
            active
            size="small"
            style={{ width: '80%', minWidth: 60 }}
            block={false}
          />
        ),
      }));
    }

    return columns.map((col) => ({
      title: col,
      dataIndex: col,
      key: col,
      ellipsis: true,
      width: DEFAULT_COL_WIDTH,
    }));
  }, [columns, loading]);

  const dataSource: DataRow[] = useMemo(() => {
    if (loading) {
      return buildSkeletonRows(columns.length || 5, LOADING_ROW_COUNT);
    }
    return rows.map((row, i) => ({ _key: i, ...row }));
  }, [loading, rows, columns.length]);

  const hasData = !loading && rows.length > 0;
  const showInfoBar = !loading && (totalRows !== undefined || executionTimeMs !== undefined);
  const showEmpty = !loading && rows.length === 0;

  return (
    <div>
      {/* Info bar: total rows + execution time */}
      {showInfoBar && (
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: 12,
            padding: '0 4px',
          }}
        >
          <Space size="middle">
            {totalRows !== undefined && (
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                共 {totalRows.toLocaleString()} 条记录
              </Typography.Text>
            )}
            {executionTimeMs !== undefined && (
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                查询耗时 {executionTimeMs < 1000
                  ? `${executionTimeMs}ms`
                  : `${(executionTimeMs / 1000).toFixed(2)}s`}
              </Typography.Text>
            )}
          </Space>

          {hasData && (
            <Button
              size="small"
              icon={<DownloadOutlined />}
              onClick={handleExport}
            >
              导出 CSV
            </Button>
          )}
        </div>
      )}

      {/* Empty state — shown before info bar so it fills the area cleanly */}
      {showEmpty && (
        <Empty
          image={<InboxOutlined style={{ fontSize: 64, color: '#bfbfbf' }} />}
          description="暂无数据"
          style={{ padding: '48px 0' }}
        />
      )}

      {/* Loading skeleton or data table */}
      {(loading || hasData) && (
        <Table<DataRow>
          columns={tableColumns}
          dataSource={dataSource}
          rowKey="_key"
          size="small"
          loading={false} // we render our own skeleton rows, not antd's spinner
          showHeader={!loading || columns.length > 0}
          scroll={{
            x: 'max-content',
            y: maxHeight,
          }}
          virtual
          pagination={false}
          locale={{
            emptyText: (
              <Empty
                image={null}
                description={null}
              />
            ),
          }}
        />
      )}
    </div>
  );
};

export default React.memo(DataPreview);
