export type BundledOllamaPullProgress = {
  model: string;
  status: string;
  completed: number | null;
  total: number | null;
  done: boolean;
};

function progressPercent(progress: BundledOllamaPullProgress): number | null {
  if (
    progress.total === null
    || progress.completed === null
    || progress.total <= 0
  ) {
    return null;
  }
  return Math.min(100, Math.max(0, Math.round((progress.completed / progress.total) * 100)));
}

export function formatBundledOllamaPullProgress(
  progress: BundledOllamaPullProgress,
): string {
  const model = progress.model.trim() || "所选模型";
  if (progress.done) return `${model} 已准备完成，可以开始生成。`;
  const status = progress.status.trim() || "下载中";
  const percent = progressPercent(progress);
  return percent === null
    ? `正在准备 ${model}：${status}…`
    : `正在准备 ${model}：${status} ${percent}%…`;
}

export function CompanionOllamaPullProgress({
  progress,
  compact = false,
}: {
  progress: BundledOllamaPullProgress | null | undefined;
  compact?: boolean;
}) {
  if (!progress) return null;

  const percent = progressPercent(progress);
  return (
    <div
      className={`companion-ollama-pull-progress${compact ? " is-compact" : ""}`}
      role="status"
      aria-live="polite"
    >
      <div className="companion-ollama-pull-progress-heading">
        <strong>{progress.done ? "模型已准备好" : "正在准备模型"}</strong>
        <span>{progress.model}</span>
      </div>
      <small>{formatBundledOllamaPullProgress(progress)}</small>
      {percent !== null ? (
        <progress
          max={100}
          value={percent}
          aria-label={`${progress.model} 模型下载进度`}
        />
      ) : null}
    </div>
  );
}
