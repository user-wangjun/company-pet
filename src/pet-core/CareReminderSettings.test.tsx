import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CareReminderSettings } from "./CareReminderSettings";
import { DEFAULT_CARE_REMINDER_SETTINGS } from "./careReminders";

describe("CareReminderSettings", () => {
  it("renders all personalized care reminder controls", () => {
    const html = renderToStaticMarkup(
      <CareReminderSettings settings={DEFAULT_CARE_REMINDER_SETTINGS} onChange={() => {}} />,
    );
    expect(html).toContain("护眼与喝水");
    expect(html).toContain("早餐时间");
    expect(html).toContain("计划入睡时间");
    expect(html).toContain("每 40 分钟");
    expect(html).toContain("关闭卡片右侧开关只会关闭系统通知弹窗");
    expect(html).toContain("护眼与喝水系统弹窗");
    expect(html).not.toContain("喝水提醒系统弹窗");
    expect(html.match(/type="checkbox"/g)).toHaveLength(3);
  });
});
