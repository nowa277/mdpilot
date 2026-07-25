import { cn } from '@shared/utils';
import { useQuery } from '@tanstack/react-query';
import { fetchSkills } from '../api/chats.api';
import { useState, useEffect, useRef, useCallback, type KeyboardEvent } from 'react';
import type { SkillInfo } from '@shared/types/api.gen';

const CATEGORIES = [
  { key: 'workflow', label: '工作流', color: '#00cfaa', bg: 'rgba(0,207,170,0.1)', border: 'rgba(0,207,170,0.2)' },
  { key: 'ai-service', label: 'AI 服务', color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', border: 'rgba(139,92,246,0.2)' },
  { key: 'concept', label: '概念', color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', border: 'rgba(59,130,246,0.2)' },
  { key: 'troubleshooting', label: '排错', color: '#fbbf24', bg: 'rgba(251,191,36,0.1)', border: 'rgba(251,191,36,0.2)' },
] as const;

interface Props {
  mode: 'slash' | 'panel';
  filter: string;
  onSelect: (skill: SkillInfo) => void;
  onTabComplete?: (text: string) => void;
  onClose: () => void;
}

export function SlashCommandMenu({ mode, filter, onSelect, onTabComplete, onClose }: Props) {
  const { data: skills = [] } = useQuery({
    queryKey: ['skills'],
    queryFn: fetchSkills,
    staleTime: 60_000,
  });

  const commandSkills = skills.filter(s => s.command);
  const [highlightIdx, setHighlightIdx] = useState(0);
  const [activeTab, setActiveTab] = useState<string>('workflow');

  const filtered = mode === 'slash'
    ? commandSkills.filter(s => {
        const q = filter.toLowerCase().replace(/^\//, '');
        if (!q) return true;
        return s.command.toLowerCase().includes(q)
          || s.title.toLowerCase().includes(q)
          || s.tags.some(t => t.toLowerCase().includes(q));
      })
    : commandSkills.filter(s => s.category === activeTab);

  const grouped = mode === 'slash' ? CATEGORIES.map(cat => ({
    ...cat,
    skills: filtered.filter(s => s.category === cat.key),
  })).filter(g => g.skills.length > 0) : [];

  const flatList = mode === 'slash' ? filtered : [];

  useEffect(() => { setHighlightIdx(0); }, [filter, activeTab]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIdx(i => Math.min(i + 1, flatList.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const skill = flatList[highlightIdx];
      if (skill) onSelect(skill);
    } else if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      const skill = flatList[highlightIdx];
      if (skill && skill.command && onTabComplete) {
        onTabComplete(skill.command + ' ');
      }
    }
  }, [flatList, highlightIdx, onSelect, onTabComplete, onClose]);

  useEffect(() => {
    if (mode === 'slash') {
      document.addEventListener('keydown', handleKeyDown as any);
      return () => document.removeEventListener('keydown', handleKeyDown as any);
    }
  }, [mode, handleKeyDown]);

  if (commandSkills.length === 0) return null;

  if (mode === 'slash') {
    return (
      <div
        className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-white/10 bg-bg-1/95 backdrop-blur-[24px]"
        style={{ animation: 'slash-pop 0.15s ease-out' }}
      >
        <style>{`@keyframes slash-pop { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
        <div className="max-h-[320px] overflow-y-auto p-2">
          {grouped.map(group => (
            <div key={group.key}>
              <div className="px-2 py-1 font-mono text-[10px] uppercase tracking-wider text-text-3">
                {group.label}
              </div>
              {group.skills.map(skill => {
                const idx = flatList.indexOf(skill);
                const active = idx === highlightIdx;
                return (
                  <button
                    key={skill.name}
                    type="button"
                    onClick={() => onSelect(skill)}
                    className={cn(
                      'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors',
                      active ? 'bg-accent-1/8' : 'hover:bg-white/3',
                    )}
                  >
                    <span className={cn(
                      'min-w-[140px] font-mono text-xs',
                      active ? 'font-semibold text-accent-1' : 'text-text-1',
                    )}>
                      {skill.command}
                    </span>
                    <span className={cn(
                      'text-[11px]',
                      active ? 'text-text-2' : 'text-text-3',
                    )}>
                      {skill.description}
                    </span>
                  </button>
                );
              })}
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="px-3 py-4 text-center text-xs text-text-3">
              没有匹配的命令
            </div>
          )}
        </div>
        <div className="border-t border-border-1 px-3 py-1.5 text-[10px] text-text-3">
          ↑↓ 导航 · Tab 补全 · Enter 确认 · Esc 关闭
        </div>
      </div>
    );
  }

  return (
    <div
      className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-xl border border-white/10 bg-bg-1/95 backdrop-blur-[24px]"
      style={{ animation: 'slash-pop 0.15s ease-out' }}
    >
      <style>{`@keyframes slash-pop { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
      <div className="p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="font-mono text-xs text-text-2">选择技能</span>
          <span className="text-[11px] text-text-3">选中后以斜杠命令插入</span>
        </div>
        <div className="mb-2 flex gap-1.5">
          {CATEGORIES.map(cat => (
            <button
              key={cat.key}
              type="button"
              onClick={() => setActiveTab(cat.key)}
              className={cn(
                'rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors',
                activeTab === cat.key
                  ? 'border-opacity-25 text-opacity-100'
                  : 'border-border-1 text-text-3 hover:text-text-2',
              )}
              style={activeTab === cat.key ? {
                borderColor: cat.border,
                color: cat.color,
                backgroundColor: cat.bg,
              } : undefined}
            >
              {cat.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {filtered.map(skill => (
            <button
              key={skill.name}
              type="button"
              onClick={() => onSelect(skill)}
              className="rounded-lg border border-border-1 bg-white/2 p-2 text-left transition-colors hover:border-border-2 hover:bg-white/4"
            >
              <div className="mb-0.5 font-mono text-[11px] font-semibold text-text-1">
                {skill.command}
              </div>
              <div className="line-clamp-2 text-[10px] leading-snug text-text-3">
                {skill.description}
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
