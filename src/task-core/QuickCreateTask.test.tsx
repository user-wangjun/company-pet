import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import {
  EMPTY_TASK_DRAFT,
  QuickCreateTask,
  TaskDraftFields,
  buildScheduledValue,
  scheduledDateValue,
  scheduledTimeValue,
} from "./QuickCreateTask";

describe("QuickCreateTask", () => {
  test("renders every PRD creation field in the expanded form", () => {
    const html = renderToStaticMarkup(<QuickCreateTask onCreate={vi.fn()} />);

    expect(html).toContain("待办标题");
    expect(html).toContain("备注");
    expect(html).toContain("附件引用");
    expect(html).toContain("截止时间");
    expect(html).toContain("提醒时间");
    expect(html).toContain("重复");
    expect(html).toContain("优先级");
    expect(html).toContain("项目");
    expect(html).toContain("加入今天");
    expect(html).toContain("具体时间（可选）");
    expect(html).toContain('type="time"');
    expect(html).not.toContain("时间精度");
    expect(html).toContain('value="none"');
    expect(html).toContain('value="daily"');
    expect(html).toContain('value="weekly"');
    expect(html).toContain('value="custom"');
  });

  test("keeps the date required while making its time optional", () => {
    expect(buildScheduledValue("2026-07-22", "")).toEqual({
      dueAt: "2026-07-22",
      schedulePrecision: "date",
    });

    const scheduled = buildScheduledValue("2026-07-22", "14:35");
    expect(scheduled.schedulePrecision).toBe("datetime");
    expect(scheduledDateValue(scheduled.dueAt)).toBe("2026-07-22");
    expect(scheduledTimeValue(scheduled.dueAt, scheduled.schedulePrecision)).toBe("14:35");
  });

  test("renders all weekday choices for a custom repeat rule", () => {
    const html = renderToStaticMarkup(
      <TaskDraftFields
        draft={{
          ...EMPTY_TASK_DRAFT,
          remindAt: "2026-07-13T01:00:00.000Z",
          repeatType: "custom",
          repeatRule: { weekdays: [1, 3, 5] },
        }}
        onChange={vi.fn()}
      />,
    );

    expect(html).toContain("在这些星期重复");
    for (const day of ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]) {
      expect(html).toContain(day);
    }
    expect(html.match(/is-selected/g)).toHaveLength(3);
  });

  test("renders long-term dates and compact milestone editing", () => {
    const html = renderToStaticMarkup(<TaskDraftFields draft={{
      ...EMPTY_TASK_DRAFT,
      title: "毕业论文",
      kind: "long_term",
      startAt: "2026-07-01",
      dueAt: "2026-07-30",
      milestones: [{ title: "完成初稿", dueAt: "2026-07-12T06:00:00.000Z", schedulePrecision: "datetime" }],
    }} onChange={vi.fn()} />);
    expect(html).toContain("开始日期");
    expect(html).toContain("截止日期（可选）");
    expect(html).toContain("日期节点");
    expect(html).toContain("完成初稿");
    expect(html).toContain("节点 1 具体时间（可选）");
    expect(html).toContain("提前10分钟");
    expect(html).not.toContain("自定义星期");
  });
});
