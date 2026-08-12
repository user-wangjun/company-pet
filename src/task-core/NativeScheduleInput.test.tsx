import { describe, expect, test } from "vitest";
import { shouldCommitNativeScheduleValue } from "./NativeScheduleInput";

describe("NativeScheduleInput", () => {
  test("defers empty intermediate values from segmented native inputs", () => {
    expect(shouldCommitNativeScheduleValue("")).toBe(false);
    expect(shouldCommitNativeScheduleValue("14:01")).toBe(true);
    expect(shouldCommitNativeScheduleValue("2026-08-04T14:01")).toBe(true);
  });
});
