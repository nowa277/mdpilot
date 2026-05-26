import { ChatList } from '@features/chat';
import { GradientDivider } from '@shared/ui';
import { cn } from '@shared/utils';
import { NavLink } from 'react-router-dom';

const NAV = [
  { to: '/workspace', label: '工作区' },
  { to: '/cluster', label: '集群' },
];

interface SidebarProps {
  width: number;
}

export function Sidebar({ width }: SidebarProps) {
  return (
    <aside className="glass-panel flex h-full flex-col" style={{ width: `${width}px` }}>
      {/* Logo */}
      <div className="group flex items-center gap-3 px-4 py-4">
        <div className="relative flex h-11 w-11 items-center justify-center">
          <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-accent-1/30 to-accent-2/30 blur-md transition-all duration-500 group-hover:from-accent-1/50 group-hover:to-accent-2/50 group-hover:blur-lg" />
          <div className="relative flex h-full w-full items-center justify-center rounded-xl border border-white/10 bg-gradient-to-br from-bg-2/80 to-bg-3/80 backdrop-blur-xl transition-all duration-300 group-hover:border-accent-1/30 group-hover:shadow-glow-cyan">
            <span className="bg-gradient-to-br from-accent-1 via-accent-2 to-info bg-clip-text font-display text-xl font-bold text-transparent">
              M
            </span>
          </div>
        </div>
        <div className="flex flex-col">
          <span className="bg-gradient-to-r from-accent-1 via-accent-2 to-accent-1 bg-clip-text font-display text-lg font-bold tracking-tight text-transparent">
            MDPilot
          </span>
          <span className="font-mono text-[9px] uppercase tracking-wider text-text-3/60">
            Molecular Dynamics
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="px-3">
        <div className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-text-3/80">导航</div>
        <ul className="flex flex-col gap-1">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'block rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
                    isActive
                      ? 'bg-primary-cyan/10 text-primary-cyan shadow-glow-cyan'
                      : 'text-text-2 hover:bg-bg-2/50 hover:text-text-1',
                  )
                }
              >
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Gradient divider */}
      <div className="mt-4">
        <GradientDivider orientation="horizontal" />
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-hidden">
        <div className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-text-3/80">对话</div>
        <ChatList />
      </div>

      {/* Gradient divider */}
      <GradientDivider orientation="horizontal" />

      {/* Footer */}
      <div className="px-4 py-3">
        <div className="text-xs text-text-3">
          <div className="font-medium">MDPilot v0.5.2</div>
          <div className="mt-1 text-text-3/60">LLM-Driven Modular Intelligent Platform for Molecular Dynamics</div>
        </div>
      </div>
    </aside>
  );
}
