import React, { useState, useRef, useCallback } from 'react';
import { Input, Button, Spin } from 'antd';
import { RobotOutlined, SendOutlined } from '@ant-design/icons';

interface NLInputProps {
  onQuery: (prompt: string) => Promise<void>;
  loading: boolean;
  placeholder?: string;
}

const HINTS = ['近30天销售额趋势', '各品类销量对比', '用户增长Top10'];

const NLInput: React.FC<NLInputProps> = ({
  onQuery,
  loading,
  placeholder = '输入自然语言描述你想要的可视化...',
}) => {
  const [value, setValue] = useState('');
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<any>(null);

  const trimmed = value.trim();
  const showSend = !loading && trimmed.length > 0;

  const handleSubmit = useCallback(async () => {
    if (!trimmed || loading) return;
    await onQuery(trimmed);
    setValue('');
    inputRef.current?.focus();
  }, [trimmed, loading, onQuery]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const fillHint = useCallback(
    (hint: string) => {
      setValue(hint);
      inputRef.current?.focus();
    },
    [],
  );

  // ---------- dynamic border / shadow ----------
  const inputBorderColor = focused ? '#1677ff' : loading ? '#e8e8e8' : '#e0e0e0';
  const inputBoxShadow = focused
    ? '0 0 0 3px rgba(22, 119, 255, 0.12)'
    : loading
      ? 'none'
      : '0 1px 4px rgba(0, 0, 0, 0.04)';

  const containerStyle: React.CSSProperties = {
    position: 'relative',
    display: 'flex',
    alignItems: 'center',
    height: 52,
    borderRadius: 28,
    background: loading ? '#f5f5f5' : '#fff',
    border: `2px solid ${inputBorderColor}`,
    boxShadow: inputBoxShadow,
    transition: 'border-color 0.25s, box-shadow 0.25s, background 0.25s',
    overflow: 'hidden',
  };

  const iconStyle: React.CSSProperties = {
    position: 'absolute',
    left: 18,
    fontSize: 20,
    color: focused ? '#1677ff' : '#bfbfbf',
    zIndex: 1,
    pointerEvents: 'none',
    transition: 'color 0.25s',
  };

  const inputStyle: React.CSSProperties = {
    height: '100%',
    paddingLeft: 48,
    paddingRight: showSend || loading ? 50 : 18,
    fontSize: 15,
    borderRadius: 0,
    border: 'none',
    boxShadow: 'none',
    background: 'transparent',
  };

  const rightBtnStyle: React.CSSProperties = {
    position: 'absolute',
    right: 6,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  };

  // ---------- render ----------
  return (
    <div>
      {/* ----- input row ----- */}
      <div style={containerStyle}>
        <RobotOutlined style={iconStyle} />

        <Input
          ref={inputRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={loading}
          style={inputStyle}
        />

        <div style={rightBtnStyle}>
          {loading ? (
            <Spin size="small" />
          ) : showSend ? (
            <Button
              type="primary"
              shape="circle"
              icon={<SendOutlined />}
              onClick={handleSubmit}
              style={{
                width: 38,
                height: 38,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(22, 119, 255, 0.3)',
              }}
            />
          ) : null}
        </div>
      </div>

      {/* ----- hint row ----- */}
      <div
        style={{
          marginTop: 10,
          paddingLeft: 4,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{
            color: '#999',
            fontSize: 12,
            whiteSpace: 'nowrap',
            lineHeight: '24px',
          }}
        >
          试试：
        </span>
        {HINTS.map((hint) => (
          <span
            key={hint}
            onClick={() => fillHint(hint)}
            style={{
              color: '#1677ff',
              fontSize: 12,
              cursor: 'pointer',
              padding: '3px 12px',
              background: 'rgba(22, 119, 255, 0.06)',
              borderRadius: 12,
              lineHeight: '22px',
              whiteSpace: 'nowrap',
              border: '1px solid transparent',
              transition: 'background 0.2s, border-color 0.2s',
              userSelect: 'none',
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(22, 119, 255, 0.12)';
              (e.currentTarget as HTMLElement).style.borderColor = 'rgba(22, 119, 255, 0.25)';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.background = 'rgba(22, 119, 255, 0.06)';
              (e.currentTarget as HTMLElement).style.borderColor = 'transparent';
            }}
          >
            {hint}
          </span>
        ))}
      </div>
    </div>
  );
};

export default NLInput;
