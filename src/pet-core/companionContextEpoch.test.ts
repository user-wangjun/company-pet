import { describe, expect, test } from "vitest";
import {
  createCompanionContextEpoch,
  isExplicitCompanionTopicChange,
} from "./companionContextEpoch";

describe("companion context epoch boundary", () => {
  test("recognizes only explicit topic changes", () => {
    expect(isExplicitCompanionTopicChange("换个话题吧")).toBe(true);
    expect(isExplicitCompanionTopicChange("先不聊这个了，我们说点别的")).toBe(true);
    expect(isExplicitCompanionTopicChange("继续刚才那件事")).toBe(false);
    expect(isExplicitCompanionTopicChange("今天有点累")).toBe(false);
  });

  test("creates distinct internal epochs without a persisted chat record", () => {
    const first = createCompanionContextEpoch();
    const second = createCompanionContextEpoch();

    expect(second).toBeGreaterThan(first);
  });
});
