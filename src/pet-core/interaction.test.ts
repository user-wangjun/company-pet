import { describe, expect, test } from "vitest";
import {
  DESKTOP_ICON_INTERACTION_COOLDOWN_MS,
  DESKTOP_ICON_INTERACTION_DELAY_MS,
  HOVER_EAT_DELAY_MS,
  findDesktopIconTarget,
  formatDesktopIconBubbleText,
  formatDesktopIconWrapBubbleText,
  getDesktopIconHugAnimationName,
  getDesktopIconArtworkBounds,
  getDesktopIconHugLayerBounds,
  getDesktopIconWrapWindowPosition,
  getHoverFishAnimationSequence,
  getPetContextMenuAction,
  getDraggedWindowPosition,
  isPrimaryButtonPressed,
  isPointerCancellation,
  shouldStartDrag,
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

  test("positions the pet window so the icon lands in the holding pose", () => {
    expect(
      getDesktopIconWrapWindowPosition(
        { title: "浏览器", x: 400, y: 300, width: 74, height: 82 },
        { width: 165, height: 155 },
      ),
    ).toEqual({ x: 361, y: 206 });
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
