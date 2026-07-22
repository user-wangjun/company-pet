import { useState } from "react";
import { buildDailyTaskReview, formatProjectName } from "./taskReview";
import type { DailyReviewTone } from "./taskReview";
import type { TaskDatabase } from "./types";

type Props = {
  database: TaskDatabase;
  speakerName?: string;
  speakerTexts?: Partial<Record<DailyReviewTone, string>>;
};

function priorityLabel(priority: "low" | "normal" | "high"): string {
  if (priority === "high") return "高优先级";
  if (priority === "low") return "低优先级";
  return "普通";
}

function fallbackSpeakerText(tone: DailyReviewTone): string {
  if (tone === "at_least_half") return "今天完成了不少，辛苦了。";
  if (tone === "below_half") return "今天已经迈出了一步，剩下的我们慢慢来。";
  return "今天还没有留下完成记录，明天我们从一件小事开始吧。";
}

export function TaskReviewPanel({
  database,
  speakerName = "桌宠",
  speakerTexts,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const review = buildDailyTaskReview(database);
  const voice = speakerTexts?.[review.tone]?.trim() || fallbackSpeakerText(review.tone);

  return (
    <section className={`task-review-panel is-${review.tone}`} aria-label="今日回顾">
      <header className="task-review-summary">
        <div>
          <p>今日回顾</p>
          <h3>{review.headline}</h3>
        </div>
        <div className="task-review-score" aria-label={review.completionRate === null ? "暂无今日任务" : `今天完成率 ${review.completionLabel}`}>
          <strong>{review.completionLabel}</strong>
          <span>{review.completionRate === null ? "今日" : `${review.completedCount} / ${review.effectiveItemCount}`}</span>
        </div>
        <button className="task-review-toggle" type="button" aria-expanded={expanded} onClick={() => setExpanded((value) => !value)}>{expanded ? "收起回顾" : "展开回顾"}</button>
      </header>

      {expanded && <div className="task-review-detail">
      <div className="task-review-stats">
        <span><b>{review.postponedCount}</b> 延期</span>
        <span><b>{review.cancelledCount}</b> 取消</span>
        <span><b>{review.overdueCount}</b> 过期</span>
        <span><b>{review.remainingTodayCount}</b> 今日剩余</span>
      </div>

      {(review.longTermProgress.length > 0 || review.completedLongTermTasks.length > 0) && (
        <section className="task-review-long-term" aria-label="长期任务进度">
          <h4>长期任务</h4>
          {review.completedLongTermTasks.map((task) => <p key={task.id}><strong>{task.title}</strong><span>今天完成整个周期</span></p>)}
          {review.longTermProgress.slice(0, 3).map((progress) => (
            <p key={progress.task.id}>
              <strong>{progress.task.title}</strong>
              <span>{progress.completedMilestones} / {progress.totalMilestones} 个节点已完成{progress.remainingDays === null ? " · 持续进行" : progress.remainingDays >= 0 ? ` · 还剩 ${progress.remainingDays} 天` : " · 周期已结束"}</span>
            </p>
          ))}
        </section>
      )}

      <div className="task-review-columns">
        <section>
          <h4>做得不错</h4>
          {review.completedTasks.length > 0 ? (
            <ul>
              {review.completedTasks.map(({ entry, task }) => (
                <li key={entry.id}>
                  <span>✓</span>
                  <strong>{task.title}</strong>
                </li>
              ))}
            </ul>
          ) : (
            <p>还没有完成记录，先完成一件小事也算开始。</p>
          )}
        </section>

        <section>
          <h4>明天先看</h4>
          {review.tomorrowFocus.length > 0 ? (
            <ul>
              {review.tomorrowFocus.map((task) => (
                <li key={task.id}>
                  <span>{task.priority === "high" ? "!" : "·"}</span>
                  <strong>{task.title}</strong>
                  <small>{priorityLabel(task.priority)}</small>
                </li>
              ))}
            </ul>
          ) : (
            <p>暂时没有需要接住的事项，可以安心收尾。</p>
          )}
        </section>
      </div>

      {review.projectHighlights.length > 0 && (
        <div className="task-review-projects" aria-label="项目分布">
          {review.projectHighlights.map((project) => (
            <span key={project.projectId}>
              {formatProjectName(project.projectId)} <b>{project.count}</b>
            </span>
          ))}
        </div>
      )}

      <blockquote>
        <span>{speakerName}想说</span>
        <p>{voice}</p>
      </blockquote>
      </div>}
    </section>
  );
}
