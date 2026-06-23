import { describe, expect, test } from "vitest";
import {
  DESKTOP_ICON_INTERACTION_COOLDOWN_MS,
  DESKTOP_ICON_INTERACTION_DELAY_MS,
  HOVER_EAT_DELAY_MS,
  findDesktopIconTarget,
  getDesktopIconBumpWindowPosition,
  formatDesktopIconBubbleText,
  formatDesktopIconWrapBubbleText,
  getDesktopIconHugAnimationName,
  getDesktopIconArtworkBounds,
  getDesktopIconHugLayerBounds,
  getDesktopIconWrapWindowPosition,
  getHoverFishAnimationSequence,
  getPetCareReminderAction,
  getPetClickAction,
  getPetContextMenuAction,
  getPetDesktopIconInteractionAction,
  getPetDragEndAction,
  getPetDragStartAction,
  getPetHoverEatingAction,
  getPetIdleAnimationName,
  getPetIdleBubbleText,
  getPetIdleQuirkActions,
  getTimedPetCareReminder,
  getDraggedWindowPosition,
  isPrimaryButtonPressed,
  isPointerCancellation,
  shouldStartDrag,
  shouldResumeHoverAfterInteraction,
  shouldTriggerHoverEat,
  updateDesktopIconInteraction,
} from "./interaction";

describe("desktop pet interaction rules", () => {
  test("starts dragging only after the pointer moves past the threshold", () => {
    expect(shouldStartDrag({ startX: 100, startY: 100, x: 103, y: 103 })).toBe(
      false,
    );
    expect(shouldStartDrag({ startX: 100, startY: 100, x: 108, y: 100 })).toBe(
      true,
    );
  });

  test("requires the primary button to still be held for drag movement", () => {
    expect(isPrimaryButtonPressed(0)).toBe(false);
    expect(isPrimaryButtonPressed(1)).toBe(true);
    expect(isPrimaryButtonPressed(2)).toBe(false);
    expect(isPrimaryButtonPressed(3)).toBe(true);
  });

  test("converts logical pointer movement into physical window movement", () => {
    expect(
      getDraggedWindowPosition({
        startPointerX: 200,
        startPointerY: 300,
        pointerX: 220,
        pointerY: 270,
        startWindowX: 500,
        startWindowY: 600,
        scaleFactor: 1.5,
      }),
    ).toEqual({ x: 530, y: 555 });
  });

  test("triggers hover eat only after the hover delay while not dragging", () => {
    expect(
      shouldTriggerHoverEat({
        hoverStartedAt: 1000,
        now: 1000 + HOVER_EAT_DELAY_MS - 1,
        isDragging: false,
      }),
    ).toBe(false);
    expect(
      shouldTriggerHoverEat({
        hoverStartedAt: 1000,
        now: 1000 + HOVER_EAT_DELAY_MS,
        isDragging: false,
      }),
    ).toBe(true);
    expect(
      shouldTriggerHoverEat({
        hoverStartedAt: 1000,
        now: 1000 + HOVER_EAT_DELAY_MS,
        isDragging: true,
      }),
    ).toBe(false);
  });

  test("does not immediately rearm hover actions after a click", () => {
    expect(shouldResumeHoverAfterInteraction("click")).toBe(false);
    expect(shouldResumeHoverAfterInteraction("drag")).toBe(true);
  });

  test("does not treat normal pointer capture loss as a canceled interaction", () => {
    expect(isPointerCancellation("lostpointercapture")).toBe(false);
    expect(isPointerCancellation("pointercancel")).toBe(true);
  });

  test("keeps the pet open when right-clicking the pet body", () => {
    expect(getPetContextMenuAction()).toBe("keep-open");
  });

  test("plays fish chasing before the fish eating animation", () => {
    expect(getHoverFishAnimationSequence()).toEqual(["fishChase", "fishEat"]);
  });

  test("uses ikun-specific idle animation and self-introduction bubble", () => {
    expect(getPetIdleAnimationName("ikun")).toBe("crouchAlert");
    expect(getPetIdleBubbleText("ikun", "fallback bubble")).toBe(
      "中分头，背带裤，我是ikun你记住",
    );
    expect(getPetIdleAnimationName("xiaoju-cat")).toBe("idle");
    expect(getPetIdleBubbleText("xiaoju-cat", "fallback bubble")).toBe(
      "fallback bubble",
    );
  });

  test("maps ikun click and drag interactions to the requested action rows", () => {
    expect(getPetDragStartAction("ikun")).toMatchObject({
      animation: "fishChase",
      sound: "fishChase",
    });
    expect(getPetDragEndAction("ikun")).toMatchObject({
      animation: "crouchAlert",
      bubbleText: "中分头，背带裤，我是ikun你记住",
    });
    expect(getPetClickAction("ikun", 1)).toMatchObject({
      animation: "gnawFish",
      sound: "gnawFish",
      bubbleText: "丢球。",
    });
    expect(getPetClickAction("ikun", 2)).toMatchObject({
      animation: "fishEat",
      sound: "fishEat",
      bubbleText: "鸡你太美",
    });
    expect(getPetClickAction("ikun", 3)).toBeNull();
  });

  test("keeps default pet click and drag interactions unchanged", () => {
    expect(getPetDragStartAction("xiaoju-cat")).toMatchObject({
      animation: "drag",
      sound: "drag",
    });
    expect(getPetClickAction("xiaoju-cat", 1)).toMatchObject({
      animation: "tickle",
      sound: "tickle",
      bubbleText: "哼，还行。",
    });
    expect(getPetClickAction("xiaoju-cat", 2)).toEqual({
      sequence: "hover-fish",
    });
  });

  test("maps suan-bird drag start and end to the flight row", () => {
    expect(getPetDragStartAction("suan-bird")).toEqual({
      animation: "drag",
      sound: "drag",
      bubbleText: "啾，起飞！",
    });
    expect(getPetDragEndAction("suan-bird")).toEqual({
      animation: "drag",
      sound: "drag_end",
      bubbleText: "平稳落地。",
      durationMs: 350,
    });
  });

  test("maps suan-bird clicks to dedicated action rows", () => {
    expect(getPetClickAction("suan-bird", 1)).toEqual({
      animation: "tickle",
      sound: "tickle",
      bubbleText: "啾！蒜鸟收到啦。",
      durationMs: 1400,
    });
    expect(getPetClickAction("suan-bird", 2)).toEqual({
      animation: "fishChase",
      sound: "fishChase",
      bubbleText: "蒜鸟蒜鸟，都不yong易；",
      durationMs: 2000,
    });
    expect(getPetClickAction("suan-bird", 3)).toBeNull();
  });

  test("maps ds interactions to whale-specific action rows", () => {
    expect(getPetIdleAnimationName("ds")).toBe("idle");
    expect(getPetIdleBubbleText("ds", "fallback bubble")).toBe(
      "fallback bubble",
    );
    expect(getPetDragStartAction("ds")).toMatchObject({
      animation: "drag",
      sound: "drag",
      bubbleText: "跳一跳，换个地方看！",
    });
    expect(getPetDragEndAction("ds")).toMatchObject({
      animation: "idle",
      bubbleText: "这儿也不错。",
    });
    expect(getPetClickAction("ds", 1)).toEqual({
      animation: "tickle",
      sound: "tickle",
      durationMs: 1200,
    });
    expect(getPetClickAction("ds", 2)).toEqual({
      sequence: "hover-fish",
    });
    expect(getPetClickAction("ds", 3)).toBeNull();
  });

  test("does not reuse click actions for pets without a dedicated hover action", () => {
    expect(getPetHoverEatingAction("ikun")).toBeNull();
    expect(getPetHoverEatingAction("suan-bird")).toBeNull();
    expect(getPetHoverEatingAction("xiaoju-cat")).toEqual({
      sequence: "hover-fish",
    });
  });

  test("uses bie-ganmao for ikun care reminders", () => {
    expect(getPetCareReminderAction("ikun", "eyeCare")).toEqual({
      animation: "tickle",
      sound: "care_reminder",
      bubbleText: "ikun们，看很久电脑了，要注意休息",
      durationMs: 8000,
    });
  });

  test("uses yawning for ds care reminders", () => {
    expect(getPetCareReminderAction("ds", "water")).toEqual({
      animation: "gnawFish",
      sound: "care_reminder",
      durationMs: 3200,
    });
  });

  test("does not add meal or sleep reminder actions to existing pets", () => {
    expect(getPetCareReminderAction("ikun", "meal")).toBeNull();
    expect(getPetCareReminderAction("ikun", "sleep")).toBeNull();
    expect(getPetCareReminderAction("ds", "meal")).toBeNull();
    expect(getPetCareReminderAction("ds", "sleep")).toBeNull();
    expect(getPetCareReminderAction("xiaoju-cat", "meal")).toBeNull();
  });

  test("maps suan-bird reminders to the approved action rows", () => {
    expect(getPetCareReminderAction("suan-bird", "water")).toEqual({
      animation: "crouchAlert",
      sound: "care_reminder",
      bubbleText: "喝口水吧，蒜鸟陪你一起补充水分。",
      durationMs: 3200,
    });
    expect(getPetCareReminderAction("suan-bird", "eyeCare")).toEqual({
      animation: "hugFish",
      sound: "care_reminder",
      bubbleText: "看看远处，让眼睛休息一下。",
      durationMs: 3200,
    });
    expect(getPetCareReminderAction("suan-bird", "meal")).toEqual({
      animation: "gnawFish",
      sound: "care_reminder",
      bubbleText: "到饭点啦，先好好吃饭。",
      durationMs: 3600,
    });
    expect(getPetCareReminderAction("suan-bird", "sleep")).toEqual({
      animation: "fishEat",
      sound: "care_reminder",
      bubbleText: "该休息啦，蒜鸟先钻进被窝了。",
      durationMs: 8000,
    });
  });

  test("selects meal and overnight reminders once per time slot", () => {
    expect(
      getTimedPetCareReminder(new Date(2026, 5, 21, 7, 30), null),
    ).toEqual({ kind: "meal", key: "2026-06-21:meal-breakfast" });
    expect(
      getTimedPetCareReminder(new Date(2026, 5, 21, 11, 30), null),
    ).toEqual({ kind: "meal", key: "2026-06-21:meal-lunch" });
    expect(
      getTimedPetCareReminder(new Date(2026, 5, 21, 18, 30), null),
    ).toEqual({ kind: "meal", key: "2026-06-21:meal-dinner" });

    const bedtime = getTimedPetCareReminder(
      new Date(2026, 5, 21, 23, 30),
      null,
    );
    expect(bedtime).toEqual({
      kind: "sleep",
      key: "2026-06-21:sleep",
    });
    expect(
      getTimedPetCareReminder(
        new Date(2026, 5, 22, 1, 0),
        bedtime?.key ?? null,
      ),
    ).toBeNull();
  });

  test("skips timed reminders outside a window or after the slot played", () => {
    expect(
      getTimedPetCareReminder(new Date(2026, 5, 21, 14, 0), null),
    ).toBeNull();
    expect(
      getTimedPetCareReminder(
        new Date(2026, 5, 21, 7, 45),
        "2026-06-21:meal-breakfast",
      ),
    ).toBeNull();
  });

  test("offers ds idle quirks for spinning, yawning, peeking, and happy settling", () => {
    const actions = getPetIdleQuirkActions("ds");

    expect(actions).toEqual([
      {
        animation: "fishEat",
        sound: "fishEat",
        duration: 2200,
      },
      {
        animation: "crouchAlert",
        sound: "crouchAlert",
        duration: 2600,
      },
      {
        animation: "gnawFish",
        sound: "gnawFish",
        duration: 3000,
      },
      {
        animation: "hugFish",
        sound: "hugFish",
        duration: 2600,
      },
      {
        animation: "tickle",
        sound: "tickle",
        duration: 1800,
      },
    ]);
    for (const action of actions) {
      expect(action).not.toHaveProperty("text");
    }
  });

  test("selects the nearest desktop icon when the pet is close enough", () => {
    const target = findDesktopIconTarget(
      { x: 100, y: 80, width: 165, height: 155 },
      [
        { title: "远处应用", x: 360, y: 220, width: 74, height: 82 },
        { title: "浏览器", x: 152, y: 178, width: 74, height: 82 },
      ],
    );

    expect(target?.title).toBe("浏览器");
    expect(target?.key).toBe("浏览器:152:178:74:82");
  });

  test("selects only right-side desktop icons for ikun shoulder hits", () => {
    const target = findDesktopIconTarget(
      { x: 100, y: 80, width: 165, height: 155 },
      [
        { title: "左边更近", x: 130, y: 178, width: 74, height: 82 },
        { title: "右边应用", x: 210, y: 178, width: 74, height: 82 },
      ],
      undefined,
      { side: "right" },
    );

    expect(target?.title).toBe("右边应用");
  });

  test("ignores desktop icons beyond the interaction distance", () => {
    expect(
      findDesktopIconTarget(
        { x: 10, y: 10, width: 165, height: 155 },
        [{ title: "太远了", x: 400, y: 400, width: 74, height: 82 }],
      ),
    ).toBeNull();
  });

  test("triggers desktop icon action only after staying near it and cooling down", () => {
    const first = updateDesktopIconInteraction({
      now: 1000,
      state: {
        activeIconKey: null,
        firstSeenAt: null,
        lastTriggeredAt: null,
      },
      target: {
        title: "回收站",
        key: "recycle-bin",
        distance: 0,
        x: 120,
        y: 180,
        width: 74,
        height: 82,
      },
    });

    expect(first.shouldInteract).toBe(false);
    expect(first.nextState.activeIconKey).toBe("recycle-bin");
    expect(first.nextState.firstSeenAt).toBe(1000);

    const ready = updateDesktopIconInteraction({
      now: 1000 + DESKTOP_ICON_INTERACTION_DELAY_MS,
      state: first.nextState,
      target: first.target,
    });

    expect(ready.shouldInteract).toBe(true);
    expect(ready.nextState.lastTriggeredAt).toBe(
      1000 + DESKTOP_ICON_INTERACTION_DELAY_MS,
    );

    const coolingDown = updateDesktopIconInteraction({
      now: 1000 + DESKTOP_ICON_INTERACTION_DELAY_MS + 1000,
      state: ready.nextState,
      target: ready.target,
    });

    expect(coolingDown.shouldInteract).toBe(false);

    const cooled = updateDesktopIconInteraction({
      now:
        1000 +
        DESKTOP_ICON_INTERACTION_DELAY_MS +
        DESKTOP_ICON_INTERACTION_COOLDOWN_MS,
      state: ready.nextState,
      target: ready.target,
    });

    expect(cooled.shouldInteract).toBe(true);
  });

  test("resets the active desktop icon when the pet moves away", () => {
    const result = updateDesktopIconInteraction({
      now: 2000,
      state: {
        activeIconKey: "folder",
        firstSeenAt: 1000,
        lastTriggeredAt: 1500,
      },
      target: null,
    });

    expect(result.shouldInteract).toBe(false);
    expect(result.nextState).toEqual({
      activeIconKey: null,
      firstSeenAt: null,
      lastTriggeredAt: 1500,
    });
  });

  test("keeps desktop icon bubble text short and safe", () => {
    expect(formatDesktopIconBubbleText("  Visual Studio Code  ")).toBe(
      "拍拍 Visual Studio…",
    );
    expect(formatDesktopIconBubbleText("")).toBe("拍拍这个图标。");
  });

  test("uses a real holding pose instead of idle when hugging a desktop icon", () => {
    expect(getDesktopIconHugAnimationName()).toBe("iconHug");
  });

  test("uses tie-shan-kao instead of icon hugging for ikun desktop icon interaction", () => {
    expect(getPetDesktopIconInteractionAction("ikun")).toEqual({
      animation: "drag",
      sound: "drag",
      bubbleText: "姬霓太美",
      durationMs: 1800,
    });
    expect(getPetDesktopIconInteractionAction("xiaoju-cat")).toEqual({
      animation: "iconHug",
      sound: "iconHug",
      bubbleText: "抱住了",
    });
  });

  test("uses curious peeking for ds desktop icon interaction", () => {
    expect(getPetDesktopIconInteractionAction("ds")).toEqual({
      animation: "hugFish",
      sound: "hugFish",
      bubbleText: "探头看看这个图标。",
      durationMs: 2400,
    });
  });

  test("positions the pet window so the icon lands in the holding pose", () => {
    expect(
      getDesktopIconWrapWindowPosition(
        { title: "浏览器", x: 400, y: 300, width: 74, height: 82 },
        { width: 165, height: 155 },
      ),
    ).toEqual({ x: 361, y: 206 });
  });

  test("positions ikun just left of the target icon before the shoulder hit", () => {
    expect(
      getDesktopIconBumpWindowPosition(
        { title: "浏览器", x: 400, y: 300, width: 74, height: 82 },
        { width: 165, height: 155 },
      ),
    ).toEqual({ x: 280, y: 207 });
  });

  test("places the hugged icon reveal at the held object position inside the pet window", () => {
    expect(
      getDesktopIconHugLayerBounds(
        { title: "浏览器", x: 400, y: 300, width: 74, height: 82 },
        { x: 361, y: 206 },
        1,
      ),
    ).toEqual({ x: 51, y: 101, width: 51, height: 51 });

    expect(
      getDesktopIconHugLayerBounds(
        { title: "浏览器", x: 800, y: 600, width: 148, height: 164 },
        { x: 722, y: 412 },
        2,
      ),
    ).toEqual({ x: 51, y: 101, width: 51, height: 51 });
  });


  test("captures only the artwork part of a desktop icon", () => {
    expect(
      getDesktopIconArtworkBounds({
        title: "浏览器",
        x: 400,
        y: 300,
        width: 74,
        height: 82,
      }),
    ).toEqual({ x: 412, y: 307, width: 51, height: 51 });
  });

  test("keeps desktop icon wrap bubble text short and safe", () => {
    expect(formatDesktopIconWrapBubbleText("  Visual Studio Code  ")).toBe(
      "抱住了",
    );
    expect(formatDesktopIconWrapBubbleText("")).toBe("抱住了");
  });
});
