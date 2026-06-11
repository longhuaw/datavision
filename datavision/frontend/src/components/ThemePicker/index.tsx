import React from 'react';

interface ThemeOption {
  key: string;
  label: string;
  previewStyle: React.CSSProperties;
  accentColor: string;
}

const THEMES: ThemeOption[] = [
  {
    key: 'default',
    label: '浅色',
    previewStyle: { background: '#ffffff' },
    accentColor: '#1677ff',
  },
  {
    key: 'dark',
    label: '暗黑',
    previewStyle: { background: '#141414' },
    accentColor: '#1677ff',
  },
  {
    key: 'tech-blue',
    label: '科技蓝',
    previewStyle: {
      background: 'linear-gradient(135deg, #0a1628 0%, #1a2a4a 100%)',
    },
    accentColor: '#1890ff',
  },
  {
    key: 'business-green',
    label: '商务绿',
    previewStyle: {
      background: 'linear-gradient(135deg, #0a2816 0%, #1a4a2a 100%)',
    },
    accentColor: '#52c41a',
  },
  {
    key: 'midnight',
    label: '极夜紫',
    previewStyle: {
      background: 'linear-gradient(135deg, #0f0c29 0%, #24243e 100%)',
    },
    accentColor: '#722ed1',
  },
];

interface ThemePickerProps {
  value: string;
  onChange: (theme: string) => void;
}

const ThemePicker: React.FC<ThemePickerProps> = ({ value, onChange }) => {
  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
      {THEMES.map((theme) => {
        const selected = value === theme.key;

        return (
          <div
            key={theme.key}
            onClick={() => onChange(theme.key)}
            style={{
              cursor: 'pointer',
              textAlign: 'center',
              userSelect: 'none',
            }}
          >
            <div
              style={{
                width: 60,
                height: 40,
                borderRadius: 6,
                border: selected
                  ? `2px solid ${theme.accentColor}`
                  : '2px solid #e8e8e8',
                boxSizing: 'border-box',
                boxShadow: selected
                  ? `0 0 6px ${theme.accentColor}40`
                  : undefined,
                overflow: 'hidden',
                position: 'relative',
                transition: 'border-color 0.2s, box-shadow 0.2s',
                ...theme.previewStyle,
              }}
            >
              {selected && (
                <div
                  style={{
                    position: 'absolute',
                    top: 2,
                    right: 2,
                    width: 14,
                    height: 14,
                    borderRadius: '50%',
                    background: theme.accentColor,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 9,
                    color: '#fff',
                    lineHeight: 1,
                  }}
                >
                  ✓
                </div>
              )}
            </div>
            <div
              style={{
                fontSize: 12,
                marginTop: 4,
                color: selected ? theme.accentColor : '#666',
                fontWeight: selected ? 600 : 400,
                transition: 'color 0.2s',
              }}
            >
              {theme.label}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ThemePicker;
