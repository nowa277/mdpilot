import { useChatUiStore } from '../store/chat-ui.store';

export function ToolModuleManager() {
  const modules = useChatUiStore((s) => s.toolModules);
  // eslint-disable-next-line @typescript-eslint/unbound-method
  const toggleModule = useChatUiStore((s) => s.toggleToolModule);

  return (
    <div className="right-panel-section">
      <div className="panel-title">
        <span>工具模块管理</span>
        <span></span>
      </div>
      <p className="settings-hint">
        查看每个工具的运行节点、默认参数、依赖状态，并手动选择是否启用。
      </p>
      <div className="tool-config-list">
        {modules.map((tool) => (
          <div key={tool.id} className={`tool-config ${tool.enabled ? '' : 'disabled'}`}>
            <div className="tool-config-head">
          <div className="tool-config-icon">{getToolIcon(tool.tool)}</div>
              <div className="tool-config-main">
                <div className="tool-config-name">{tool.label}</div>
         <div className="tool-config-route">{tool.route}</div>
            </div>
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={tool.enabled}
              onChange={() => toggleModule(tool.tool)}
               aria-label={`${tool.enabled ? '禁用' : '启用'} ${tool.label}`}
              />
                <span className="slider" />
              </label>
            </div>
            <div className="tool-config-desc">{tool.description}</div>
            <div className="tool-config-meta">
              {tool.tags.map((tag) => (
                <span key={tag} className={`tag ${getTagClass(tag)}`}>
                  {tag}
            </span>
          ))}
            <span className="tag info">
           {Object.entries(tool.defaults ?? {})
              .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
                  .join(', ')}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function getToolIcon(tool: string): string {
  const icons: Record<string, string> = {
    bioreason_annotate: '🔬',
    alphafold2_predict: '🧬',
    md_prep: '⚗️',
    amber_md: '💠',
    mmpbsa: '📊',
    vmd_render: '🎞️',
    bash_run: '⌘',
    knowledge_search: '📚',
  };
  return icons[tool] ?? '🔧';
}

function getTagClass(tag: string): string {
  if (tag.includes('ready')) return 'ok';
  if (tag.includes('depends') || tag.includes('optional')) return 'warn';
  return 'info';
}
