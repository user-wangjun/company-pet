import { useEffect, useState } from "react";
import type {
  MemoryEntry,
  MemoryRepository,
  MemoryStatus,
  MemoryType,
} from "./companionMemory";

type Props = {
  repository: MemoryRepository;
  petId: string;
};

const memoryTypeLabels: Record<MemoryType, string> = {
  fact: "事实",
  relationship: "关系",
  episode: "经历",
  preference: "偏好",
};

const memoryStatusLabels: Record<MemoryStatus, string> = {
  active: "使用中",
  disabled: "已禁用",
  superseded: "已被替代",
  deleted: "已删除",
};

function formatMemoryDate(value: string): string {
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "时间未知";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function scopeLabel(scope: MemoryEntry["scope"], petId: string): string {
  if (scope === "global") return "全局用户";
  return scope === `pet:${petId}` ? "当前宠物" : scope;
}

function readVisibleMemories(
  repository: MemoryRepository,
  petId: string,
): MemoryEntry[] {
  return repository
    .list({ includeDeleted: false })
    .filter(
      (entry) => entry.scope === "global" || entry.scope === `pet:${petId}`,
    );
}

function downloadMemoryExport(
  repository: MemoryRepository,
  format: "json" | "markdown",
): void {
  if (typeof document === "undefined" || typeof URL === "undefined") return;
  const content = repository.export(format, { includeDeleted: false });
  const blob = new Blob([content], {
    type: format === "json" ? "application/json" : "text/markdown",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `yuxin-companion-memory.${format === "json" ? "json" : "md"}`;
  link.click();
  URL.revokeObjectURL(url);
}

export function CompanionMemorySettings({ repository, petId }: Props) {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      setEntries(readVisibleMemories(repository, petId));
      setError("");
    } catch {
      setEntries([]);
      setError("Memory 暂时读不到了，聊天仍可以继续。" );
    }
    setEditingId(null);
    setDraft("");
  }, [petId, repository]);

  const refresh = () => {
    try {
      setEntries(readVisibleMemories(repository, petId));
      setError("");
    } catch {
      setError("Memory 暂时读不到了，聊天仍可以继续。" );
    }
  };

  const updateStatus = (id: string, status: MemoryStatus) => {
    if (!repository.update(id, { status })) {
      setError("这条 Memory 没有保存成功，请稍后再试。" );
      return;
    }
    refresh();
  };

  const saveEdit = (id: string) => {
    const content = draft.trim();
    if (!content) {
      setError("Memory 内容不能为空。" );
      return;
    }
    if (!repository.update(id, { content })) {
      setError("内容为空或包含不允许保存的敏感信息。" );
      return;
    }
    setEditingId(null);
    setDraft("");
    refresh();
  };

  return (
    <section className="companion-memory-settings" aria-label="Memory 管理">
      <header className="companion-memory-header">
        <div>
          <strong>长期 Memory</strong>
          <small>只保存你明确要求或确认的参考资料，不保存完整聊天记录。</small>
        </div>
        <div className="companion-memory-export-actions">
          <button type="button" onClick={() => downloadMemoryExport(repository, "json")}>
            导出 JSON
          </button>
          <button type="button" onClick={() => downloadMemoryExport(repository, "markdown")}>
            导出 Markdown
          </button>
        </div>
      </header>

      {error && <p className="companion-memory-error" role="alert">{error}</p>}

      {!entries.length ? (
        <div className="companion-memory-empty">
          <span aria-hidden="true">◇</span>
          <strong>还没有保存的 Memory</strong>
          <p>聊天中明确说“记住……”后，确认的内容会出现在这里。</p>
        </div>
      ) : (
        <div className="companion-memory-list">
          {entries.map((entry) => (
            <article
              className={`companion-memory-card is-${entry.status}`}
              key={entry.id}
            >
              <div className="companion-memory-card-main">
                {editingId === entry.id ? (
                  <textarea
                    aria-label="编辑 Memory 内容"
                    value={draft}
                    onChange={(event) => setDraft(event.currentTarget.value)}
                    rows={3}
                  />
                ) : (
                  <strong>{entry.content}</strong>
                )}
                <div className="companion-memory-meta">
                  <span>{memoryTypeLabels[entry.type]}</span>
                  <span>{scopeLabel(entry.scope, petId)}</span>
                  <span>{entry.source === "explicit" ? "明确要求" : "用户确认"}</span>
                  <span>{memoryStatusLabels[entry.status]}</span>
                  <span>更新于 {formatMemoryDate(entry.updatedAt)}</span>
                </div>
              </div>
              <div className="companion-memory-card-actions">
                {editingId === entry.id ? (
                  <>
                    <button type="button" onClick={() => saveEdit(entry.id)}>保存</button>
                    <button
                      type="button"
                      onClick={() => {
                        setEditingId(null);
                        setDraft("");
                      }}
                    >
                      取消
                    </button>
                  </>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setEditingId(entry.id);
                      setDraft(entry.content);
                      setError("");
                    }}
                  >
                    编辑
                  </button>
                )}
                {entry.status === "active" ? (
                  <button type="button" onClick={() => updateStatus(entry.id, "disabled")}>
                    禁用
                  </button>
                ) : entry.status === "disabled" ? (
                  <button type="button" onClick={() => updateStatus(entry.id, "active")}>
                    恢复
                  </button>
                ) : null}
                {entry.status !== "deleted" && (
                  <button type="button" onClick={() => updateStatus(entry.id, "deleted")}>
                    删除
                  </button>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

