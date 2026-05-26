import { cn } from '@shared/utils';
import { useQuery } from '@tanstack/react-query';
import { fetchSkills } from '../api/chats.api';
import { useState } from 'react';

interface Props {
  selected: string[];
  onChange: (names: string[]) => void;
}

export function SkillSelector({ selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const { data: skills = [] } = useQuery({
    queryKey: ['skills'],
    queryFn: fetchSkills,
    staleTime: 60_000,
  });

  function toggle(name: string) {
    if (selected.includes(name)) {
      onChange(selected.filter((n) => n !== name));
    } else {
      onChange([...selected, name]);
    }
  }

  function remove(name: string) {
    onChange(selected.filter((n) => n !== name));
  }

  if (skills.length === 0) return null;

  const selectedSkills = skills.filter((s) => selected.includes(s.name));

  return (
    <div>
      {/* Active chips — above the dropdown/textarea */}
      {selectedSkills.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {selectedSkills.map((s) => (
            <span
              key={s.name}
              className="inline-flex items-center gap-1 rounded-md border border-accent-1/35 bg-accent-1/10 px-2.5 py-0.5 font-mono text-[11px] font-medium text-accent-1"
            >
              {s.title}
              <button
                type="button"
                onClick={() => remove(s.name)}
                className="ml-0.5 opacity-60 hover:opacity-100"
                aria-label={`Remove ${s.title}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Skills toggle button + dropdown */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className={cn(
            'mb-2 flex h-8 items-center gap-1.5 rounded-lg border px-3 font-mono text-xs font-medium transition-all',
            selected.length > 0
              ? 'border-accent-1/40 bg-accent-1/6 text-accent-1'
              : 'border-border-1 text-text-2 hover:border-border-2 hover:bg-bg-2 hover:text-text-1',
          )}
        >
          <span className="text-sm">⚡</span>
          Skills
          {selected.length > 0 && (
            <span className="ml-0.5 inline-flex min-w-[16px] items-center justify-center rounded-full bg-accent-1/20 px-1 text-[10px] text-accent-1">
              {selected.length}
            </span>
          )}
        </button>

        {open && (
          <div className="absolute bottom-full left-0 z-50 mb-2 w-full rounded-xl border border-white/7 bg-bg-1/95 p-4 shadow-xl backdrop-blur-[28px]"
               style={{ animation: 'dropdown-in 0.2s ease-out' }}>
            <style>{`@keyframes dropdown-in { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }`}</style>
            {/* Header */}
            <div className="mb-3 flex items-center justify-between">
              <span className="font-mono text-xs font-medium text-text-2">
                ⚡ 选择 Skills（可多选）
              </span>
              <span className="text-[11px] text-text-3">
                选中后随消息发送，仅当次生效
              </span>
            </div>

            {/* Card grid — 3 columns */}
            <div className="grid grid-cols-3 gap-2">
              {skills.map((s) => {
                const isActive = selected.includes(s.name);
                return (
                  <button
                    key={s.name}
                    type="button"
                    onClick={() => toggle(s.name)}
                    className={cn(
                      'rounded-[10px] border p-2.5 text-left transition-all',
                      isActive
                        ? 'border-accent-1/35 bg-accent-1/6'
                        : 'border-border-1 bg-white/2 hover:bg-white/4 hover:border-border-2',
                    )}
                  >
                    <div
                      className={cn(
                        'mb-0.5 flex items-center gap-1.5 font-mono text-xs font-semibold',
                        isActive ? 'text-accent-1' : 'text-text-1',
                      )}
                    >
                      <span
                        className={cn(
                          'flex h-3.5 w-3.5 items-center justify-center rounded text-[9px] transition-all',
                          isActive
                            ? 'border-accent-1 bg-accent-1 text-bg-0'
                            : 'border border-border-2 text-transparent',
                        )}
                      >
                        ✓
                      </span>
                      {s.title}
                    </div>
                    <p className="mb-1.5 line-clamp-2 text-[11px] leading-snug text-text-3">
                      {s.description}
                    </p>
                    {s.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {s.tags.map((t) => (
                          <span
                            key={t}
                            className={cn(
                              'rounded-sm border px-1 py-px font-mono text-[9px]',
                              isActive
                                ? 'border-accent-1/15 text-text-3'
                                : 'border-white/6 text-text-3',
                            )}
                          >
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Inject indicator */}
            {selected.length > 0 && (
              <div className="mt-2.5 flex items-center gap-2 rounded-lg border border-accent-1/12 bg-accent-1/5 px-2.5 py-1.5">
                <span className="font-mono text-[10px] uppercase tracking-wider text-accent-1">
                  将注入 →
                </span>
                <div className="flex gap-1">
                  {selectedSkills.map((s) => (
                    <span
                      key={s.name}
                      className="rounded bg-accent-1/10 px-1.5 py-px font-mono text-[10px] text-accent-1"
                    >
                      {s.title}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
