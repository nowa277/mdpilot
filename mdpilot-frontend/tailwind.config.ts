import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'bg-0': 'var(--bg-0)',
        'bg-1': 'var(--bg-1)',
        'bg-2': 'var(--bg-2)',
        'bg-3': 'var(--bg-3)',
        'border-1': 'var(--border-1)',
        'border-2': 'var(--border-2)',
        'accent-1': 'var(--accent-1)',
        'accent-2': 'var(--accent-2)',
     'text-1': 'var(--text-1)',
        'text-2': 'var(--text-2)',
        'text-3': 'var(--text-3)',
        success: 'var(--state-success)',
     warning: 'var(--state-warning)',
        danger: 'var(--state-error)',
      info: 'var(--state-info)',
        'message-user-bg': 'rgba(15, 23, 42, 0.7)',
        'message-user-border': 'rgba(148, 163, 184, 0.15)',
        'message-agent-bg': 'rgba(0, 212, 255, 0.06)',
        'message-agent-border': 'rgba(0, 212, 255, 0.2)',
        'thinking-bg': 'rgba(183, 148, 246, 0.12)',
        'thinking-border': '#B794F6',
        'code-bg': '#0A0E1A',
        'code-header-bg': 'rgba(15, 23, 42, 0.8)',
      // 新增主题色
     'primary-pink': '#FF6B9D',
        'primary-orange': '#FFB84D',
        'primary-cyan': '#00D4FF',
        'primary-purple': '#B794F6',
        'primary-green': '#4ADE80',
      // 新增背景色
        'bg-dark': '#0A0E1A',
        'bg-darker': '#060913',
      },
      fontFamily: {
        sans: ['"Noto Sans SC"', 'system-ui', 'sans-serif'],
        display: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        chip: '6px',
        card: '8px',
      panel: '12px',
      },
      boxShadow: {
        'message-user': '0 2px 8px rgba(0, 0, 0, 0.2)',
        'message-agent': '0 2px 8px rgba(0, 212, 255, 0.1)',
      'avatar-user': '0 2px 8px rgba(255, 107, 157, 0.3)',
      'avatar-agent': '0 2px 8px rgba(0, 212, 255, 0.3)',
        'thinking-inset': 'inset 0 1px 3px rgba(0, 0, 0, 0.1)',
        // 新增发光阴影
        'glow-cyan': '0 0 20px rgba(0, 212, 255, 0.3), 0 0 40px rgba(0, 212, 255, 0.1)',
        'glow-pink': '0 0 20px rgba(255, 107, 157, 0.3), 0 0 40px rgba(255, 107, 157, 0.1)',
        'glow-orange': '0 0 20px rgba(255, 184, 77, 0.3), 0 0 40px rgba(255, 184, 77, 0.1)',
        'glow-purple': '0 0 20px rgba(183, 148, 246, 0.3), 0 0 40px rgba(183, 148, 246, 0.1)',
        'glow-green': '0 0 20px rgba(74, 222, 128, 0.3), 0 0 40px rgba(74, 222, 128, 0.1)',
      },
      backgroundImage: {
     'avatar-user': 'linear-gradient(135deg, #FFB84D, #FF6B9D)',
        'avatar-agent': 'linear-gradient(135deg, #FF6B9D, #00D4FF)',
      },
    },
  },
  plugins: [],
} satisfies Config;
