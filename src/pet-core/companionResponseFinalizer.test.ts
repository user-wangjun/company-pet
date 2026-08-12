import { describe, expect, test } from "vitest";
import { finalizeCompanionResponse } from "./companionResponseFinalizer";

describe("Companion ResponseFinalizer", () => {
  test("preserves a safe draft when the turn has no Action", () => {
    expect(finalizeCompanionResponse({
      replyDraft: "今天也辛苦啦。",
      actions: [],
    })).toBe("今天也辛苦啦。");
  });

  test.each([
    121,
    2_000,
  ])("does not truncate a safe ordinary reply of %i characters", (length) => {
    const draft = "答".repeat(length);
    expect(finalizeCompanionResponse({ replyDraft: draft, actions: [] })).toBe(draft);
  });

  test("fails closed for an empty or over-limit ordinary reply", () => {
    expect(finalizeCompanionResponse({ replyDraft: "", actions: [] })).toBeNull();
    expect(finalizeCompanionResponse({ replyDraft: "答".repeat(2_001), actions: [] })).toBeNull();
  });

  test("uses the actual successful write result instead of the model draft", () => {
    const text = finalizeCompanionResponse({
      replyDraft: "已经创建好了。",
      actions: [{
        type: "create_reminder",
        status: "succeeded",
        displayData: { title: "交报告", triggerTime: "8月12日15:00" },
      }],
    });
    expect(text).toContain("交报告");
    expect(text).toContain("提醒");
  });

  test("renders a successful reminder update from local execution data", () => {
    expect(finalizeCompanionResponse({
      replyDraft: "已经改好了。",
      actions: [{
        type: "update_reminder",
        status: "succeeded",
        displayData: { title: "交报告", triggerTime: "8月12日16:00" },
      }],
    })).toContain("已经把“交报告”提醒改到");
  });

  test.each([
    "not_found",
    "ambiguous",
    "confirmation_required",
    "rejected",
    "failed",
    "cancelled",
  ] as const)("does not claim success for %s", (status) => {
    const text = finalizeCompanionResponse({
      replyDraft: "已经完成了。",
      actions: [{ type: "complete_task", status, displayData: { title: "交报告" } }],
    });
    expect(text).not.toContain("已经完成");
    expect(text).toContain("交报告");
  });

  test.each([
    ["create_task", "已有记录，没有重复创建"],
    ["create_reminder", "已有记录，没有重复创建"],
    ["complete_task", "任务已经完成，本次无需重复完成"],
    ["update_reminder", "提醒时间未发生变化"],
    ["cancel_task", "任务已经取消，本次无需重复取消"],
    ["postpone_task", "时间没有变化，无需重复延期"],
    ["reschedule_task", "时间没有变化，无需重复改期"],
  ] as const)("uses an Action-specific duplicate message for %s", (type, phrase) => {
    const text = finalizeCompanionResponse({
      replyDraft: "已经处理了。",
      actions: [{
        type,
        status: "duplicate",
        displayData: { title: "交报告", triggerTime: "8月12日16:00" },
      }],
    });
    expect(text).toContain(phrase);
    expect(text).toContain("交报告");
  });

  test.each([
    ["create_task", "已经为你创建", "待办"],
    ["create_reminder", "已经为你创建", "提醒"],
    ["complete_task", "已经完成", "交报告"],
    ["update_reminder", "已经把", "提醒"],
    ["cancel_task", "已经取消", "任务"],
    ["postpone_task", "延期到", "任务"],
    ["reschedule_task", "改期到", "任务"],
  ] as const)("uses an Action-specific success message for %s", (type, phrase, secondary) => {
    const text = finalizeCompanionResponse({
      replyDraft: "已经处理了。",
      actions: [{
        type,
        status: "succeeded",
        displayData: { title: "交报告", triggerTime: "8月12日16:00" },
      }],
    });
    expect(text).toContain(phrase);
    expect(text).toContain(secondary);
  });

  test.each([
    "succeeded",
    "duplicate",
  ] as const)("keeps a proactive preference result independent from Action candidates: %s", (status) => {
    const text = finalizeCompanionResponse({
      replyDraft: "模型声称已经完成。",
      actions: [],
      proactivePreference: {
        type: "proactive_preference",
        action: "mute",
        status,
        displayData: { title: "交报告" },
      },
    });
    expect(text).toContain("交报告");
    expect(text).not.toContain("模型声称");
  });

  test("summarizes partial multi-Action results item by item", () => {
    const text = finalizeCompanionResponse({
      replyDraft: "都完成了。",
      actions: [
        { type: "create_task", status: "succeeded", displayData: { title: "买菜" } },
        { type: "create_reminder", status: "failed", displayData: { title: "交报告" } },
      ],
    });
    expect(text).toContain("已经为你创建“买菜”待办");
    expect(text).toContain("交报告");
    expect(text).toContain("没有处理成功");
    expect(text).not.toBe("都完成了。");
  });

  test.each([
    [["inserted", "confirmation_required"], "已记住 1 条；另有 1 条尚未保存，需要你确认。"],
    [["inserted", "failed"], "已记住 1 条；另有 1 条保存失败。"],
    [["duplicate", "confirmation_required"], "1 条已经记着；另有 1 条尚未保存，需要你确认。"],
    [["inserted", "rejected"], "已记住 1 条；另有 1 条未通过本地安全检查。"],
    [["inserted", "expired"], "已记住 1 条；另有 1 条因已过期而未保存。"],
  ] as const)("aggregates mixed Memory results without trusting the draft: %s", (statuses, expected) => {
    const text = finalizeCompanionResponse({
      replyDraft: "都记住了：候选原文不应回显。",
      actions: [],
      memory: {
        status: (statuses as readonly string[]).includes("failed") ? "failed" : "ignored",
        acceptedCount: statuses.filter((status) => status === "inserted").length,
        rejectedCount: statuses.length - statuses.filter((status) => status === "inserted").length,
        decisions: statuses.map((status, index) => ({
          index,
          status,
        })),
      },
    });
    expect(text).toBe(expected);
    expect(text).not.toContain("候选原文");
  });

  test("keeps Action success while separately reporting mixed Memory results", () => {
    const text = finalizeCompanionResponse({
      replyDraft: "都记住了。",
      actions: [{ type: "create_task", status: "succeeded", displayData: { title: "买菜" } }],
      memory: {
        status: "failed",
        acceptedCount: 1,
        rejectedCount: 1,
        decisions: [
          { index: 0, status: "inserted" },
          { index: 1, status: "failed", errorCode: "storage-failed" },
        ],
      },
    });
    expect(text).toContain("已经为你创建“买菜”待办");
    expect(text).toContain("已记住 1 条；另有 1 条保存失败。");
    expect(text).not.toContain("都记住了");
  });

  test("does not echo unsafe display fields", () => {
    const text = finalizeCompanionResponse({
      replyDraft: "已经创建好了。",
      actions: [{
        type: "create_task",
        status: "succeeded",
        displayData: { title: "password=DO_NOT_ECHO" },
      }],
    });
    expect(text).not.toContain("DO_NOT_ECHO");
    expect(text).toContain("待办");
  });

  test("does not emit a draft when Memory is cancelled", () => {
    expect(finalizeCompanionResponse({
      replyDraft: "已经记住了。",
      actions: [],
      memory: {
        status: "cancelled",
        acceptedCount: 0,
        rejectedCount: 1,
        decisions: [{ index: 0, status: "cancelled", errorCode: "turn-invalidated" }],
      },
    })).toBeNull();
  });
});
