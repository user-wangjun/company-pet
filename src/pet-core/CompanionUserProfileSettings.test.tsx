// @vitest-environment jsdom

import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, test, vi } from "vitest";
import {
  CompanionUserProfileSettings,
  type CompanionUserProfileDraftSyncOptions,
  type CompanionUserProfileDraftSyncResult,
  type CompanionUserProfileSaveLifecycle,
  synchronizeCompanionUserProfileDraft,
} from "./CompanionUserProfileSettings";
import {
  EMPTY_COMPANION_USER_PROFILE,
  type CompanionUserProfile,
  type CompanionUserProfileActionResult,
} from "./companionUserProfile";
import type { SettingsInitialization } from "./companionUserSettingsRepository";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const synchronize: (
  profile: CompanionUserProfile | null,
  feedback: CompanionUserProfileActionResult | null,
  options?: CompanionUserProfileDraftSyncOptions,
) => CompanionUserProfileDraftSyncResult = synchronizeCompanionUserProfileDraft;

function saveLifecycle(
  baseProfile: CompanionUserProfile,
  submittedProfile: CompanionUserProfile,
  result: CompanionUserProfileActionResult | null = null,
): CompanionUserProfileSaveLifecycle {
  return { id: 1, baseProfile, submittedProfile, result };
}

type Deferred<T> = {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
};

function deferred<T>(): Deferred<T> {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

function profileWithNickname(nickname: string): CompanionUserProfile {
  return { ...EMPTY_COMPANION_USER_PROFILE, nickname };
}

function saveButton(container: HTMLElement): HTMLButtonElement {
  const button = container.querySelector<HTMLButtonElement>(
    'button[type="button"].is-primary',
  );
  if (!button) throw new Error("save button not mounted");
  return button;
}

function nicknameInput(container: HTMLElement): HTMLInputElement {
  const input = container.querySelector<HTMLInputElement>('input[aria-label="用户昵称"]');
  if (!input) throw new Error("nickname input not mounted");
  return input;
}

async function flushReact(): Promise<void> {
  await act(async () => {});
}

async function mountProfileSettings(
  onSave: (
    profile: CompanionUserProfile,
  ) => CompanionUserProfileActionResult | Promise<CompanionUserProfileActionResult>,
  profile: CompanionUserProfile = profileWithNickname("initial"),
) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<CompanionUserProfileSettings profile={profile} onSave={onSave} />);
  });

  return {
    container,
    async rerender(nextProfile: CompanionUserProfile | null, settings?: SettingsInitialization) {
      await act(async () => {
        root.render(
          <CompanionUserProfileSettings
            profile={nextProfile}
            settings={settings}
            onSave={onSave}
          />,
        );
      });
    },
    async unmount() {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

async function editNickname(container: HTMLElement, nickname: string): Promise<void> {
  const input = nicknameInput(container);
  await act(async () => {
    const valueSetter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    if (!valueSetter) throw new Error("input value setter not available");
    valueSetter.call(input, nickname);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

function dispatchSaveClick(button: HTMLButtonElement): void {
  button.dispatchEvent(new MouseEvent("click", { bubbles: true }));
}

describe("CompanionUserProfileSettings", () => {
  test("renders the general personal information section without remote disclosure", () => {
    const html = renderToStaticMarkup(
      <CompanionUserProfileSettings
        profile={{
          ...EMPTY_COMPANION_USER_PROFILE,
          nickname: "阿星",
        }}
        onSave={vi.fn()}
      />,
    );

    expect(html).toContain('aria-label="个人信息"');
    expect(html).toContain("用户昵称");
    expect(html).toContain("用户性别");
    expect(html).toContain("用户邮箱");
    expect(html).toContain("用户电话");
    expect(html).toContain("保存个人信息");
    expect(html).toContain("不会进入聊天上下文或发送给 Provider");
    expect(html).not.toContain("sk-profile-test-value");
  });

  test("keeps feedback for the committed profile projection", () => {
    const feedback = { ok: true, message: "个人信息已保存在本机。" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-committed" };

    expect(synchronize(
      committed,
      feedback,
      { saveLifecycle: saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed, feedback) },
    )).toMatchObject({ feedback, saveLifecycleValid: true });
  });

  test("supports result-before-projection and projection-before-result ordering", () => {
    const feedback = { ok: true, message: "个人信息已保存在本机。" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-ordered" };
    const lifecycle = saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed);

    const resultBeforeProjection = synchronize(
      EMPTY_COMPANION_USER_PROFILE,
      feedback,
      { saveLifecycle: { ...lifecycle, result: feedback } },
    );
    expect(resultBeforeProjection).toMatchObject({ feedback, saveLifecycleValid: true });
    expect(synchronize(
      committed,
      resultBeforeProjection.feedback,
      { saveLifecycle: { ...lifecycle, result: feedback } },
    )).toMatchObject({ feedback, saveLifecycleValid: true });

    const projectionBeforeResult = synchronize(
      committed,
      null,
      { saveLifecycle: lifecycle },
    );
    expect(projectionBeforeResult).toMatchObject({ feedback: null, saveLifecycleValid: true });
    expect(synchronize(
      committed,
      feedback,
      { saveLifecycle: { ...lifecycle, result: feedback } },
    )).toMatchObject({ feedback, saveLifecycleValid: true });
  });

  test("keeps no-op save feedback", () => {
    const feedback = { ok: true, message: "个人信息没有新的变化。" };

    expect(synchronize(
      EMPTY_COMPANION_USER_PROFILE,
      feedback,
      {
        saveLifecycle: saveLifecycle(
          EMPTY_COMPANION_USER_PROFILE,
          EMPTY_COMPANION_USER_PROFILE,
          feedback,
        ),
      },
    )).toMatchObject({ feedback, saveLifecycleValid: true });
  });

  test("clears feedback when Profile becomes blocked or null", () => {
    const feedback = { ok: true, message: "旧成功" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-blocked" };
    const lifecycle = saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed, feedback);

    expect(synchronize(committed, feedback, { blocked: true, saveLifecycle: lifecycle }))
      .toMatchObject({ feedback: null, saveLifecycleValid: false });
    expect(synchronize(null, feedback, { saveLifecycle: lifecycle }))
      .toMatchObject({ feedback: null, saveLifecycleValid: false });
  });

  test("does not resurrect success after blocked recovery", () => {
    const feedback = { ok: true, message: "旧成功" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-recovered" };
    const lifecycle = saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed, feedback);
    const blocked = synchronize(null, feedback, { saveLifecycle: lifecycle });

    expect(synchronize(committed, blocked.feedback, { saveLifecycle: null }))
      .toMatchObject({ feedback: null, saveLifecycleValid: false });
  });

  test("clears feedback for an unrelated external Profile update", () => {
    const feedback = { ok: true, message: "旧成功" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-committed" };
    const unrelated = { ...committed, email: "external@example.com" };

    expect(synchronize(
      unrelated,
      feedback,
      { saveLifecycle: saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed, feedback) },
    )).toMatchObject({ feedback: null, saveLifecycleValid: false });
  });

  test("clears feedback and invalidates the save when the user edits again", () => {
    const feedback = { ok: true, message: "旧成功" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-edited" };

    expect(synchronize(
      committed,
      feedback,
      {
        clearFeedback: true,
        saveLifecycle: saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed, feedback),
      },
    )).toMatchObject({ feedback: null, saveLifecycleValid: false });
  });

  test("does not retain feedback for every Profile update", () => {
    const feedback = { ok: true, message: "旧成功" };
    const committed = { ...EMPTY_COMPANION_USER_PROFILE, nickname: "QA-committed" };

    expect(synchronize(
      { ...committed, gender: "female" },
      feedback,
      { saveLifecycle: saveLifecycle(EMPTY_COMPANION_USER_PROFILE, committed, feedback) },
    ).feedback).toBeNull();
  });

  test("keeps one physical save request locked through a pending draft edit", async () => {
    const firstSave = deferred<CompanionUserProfileActionResult>();
    const onSave = vi.fn(() => firstSave.promise);
    const mounted = await mountProfileSettings(onSave);

    try {
      await editNickname(mounted.container, "submitted");
      const button = saveButton(mounted.container);
      await act(async () => {
        dispatchSaveClick(button);
        dispatchSaveClick(button);
      });

      expect(onSave).toHaveBeenCalledTimes(1);

      await editNickname(mounted.container, "latest-draft");
      expect(nicknameInput(mounted.container).value).toBe("latest-draft");
      expect(button.disabled).toBe(true);
      expect(button.textContent).toContain("保存中");
      expect(mounted.container.querySelector('[role="status"], [role="alert"]')).toBeNull();

      await act(async () => {
        dispatchSaveClick(button);
      });
      expect(onSave).toHaveBeenCalledTimes(1);
    } finally {
      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      await mounted.unmount();
    }
  });

  test("does not let a result arriving before Owner projection replace a newer draft", async () => {
    const firstSave = deferred<CompanionUserProfileActionResult>();
    const submitted = profileWithNickname("submitted");
    const onSave = vi.fn(() => firstSave.promise);
    const mounted = await mountProfileSettings(onSave);

    try {
      await editNickname(mounted.container, submitted.nickname);
      dispatchSaveClick(saveButton(mounted.container));
      await flushReact();
      await editNickname(mounted.container, "latest-draft");

      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      expect(nicknameInput(mounted.container).value).toBe("latest-draft");

      await mounted.rerender(submitted);
      expect(nicknameInput(mounted.container).value).toBe("latest-draft");
    } finally {
      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      await mounted.unmount();
    }
  });

  test("does not let Owner projection arriving before a result replace a newer draft", async () => {
    const firstSave = deferred<CompanionUserProfileActionResult>();
    const submitted = profileWithNickname("submitted");
    const onSave = vi.fn(() => firstSave.promise);
    const mounted = await mountProfileSettings(onSave);

    try {
      await editNickname(mounted.container, submitted.nickname);
      dispatchSaveClick(saveButton(mounted.container));
      await flushReact();
      await editNickname(mounted.container, "latest-draft");

      await mounted.rerender(submitted);
      expect(nicknameInput(mounted.container).value).toBe("latest-draft");

      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      expect(nicknameInput(mounted.container).value).toBe("latest-draft");
    } finally {
      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      await mounted.unmount();
    }
  });

  test("opens only after the first request settles and submits the latest draft next", async () => {
    const firstSave = deferred<CompanionUserProfileActionResult>();
    const secondSave = deferred<CompanionUserProfileActionResult>();
    const submittedProfiles: CompanionUserProfile[] = [];
    const onSave = vi.fn((submitted: CompanionUserProfile) => {
      submittedProfiles.push(submitted);
      return submittedProfiles.length === 1 ? firstSave.promise : secondSave.promise;
    });
    const mounted = await mountProfileSettings(onSave);

    try {
      await editNickname(mounted.container, "submitted");
      dispatchSaveClick(saveButton(mounted.container));
      await flushReact();
      await editNickname(mounted.container, "latest-draft");

      expect(saveButton(mounted.container).disabled).toBe(true);
      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      expect(saveButton(mounted.container).disabled).toBe(false);

      dispatchSaveClick(saveButton(mounted.container));
      await flushReact();
      expect(onSave).toHaveBeenCalledTimes(2);
      expect(submittedProfiles[1]).toEqual(profileWithNickname("latest-draft"));
    } finally {
      firstSave.resolve({ ok: true, message: "保存结果" });
      secondSave.resolve({ ok: true, message: "第二次保存结果" });
      await flushReact();
      await mounted.unmount();
    }
  });

  test("does not overlap an old request across blocked recovery", async () => {
    const firstSave = deferred<CompanionUserProfileActionResult>();
    const onSave = vi.fn(() => firstSave.promise);
    const mounted = await mountProfileSettings(onSave);
    const blockedSettings = {
      status: "blocked",
      reason: "recovery-blocked",
    } as SettingsInitialization;

    try {
      dispatchSaveClick(saveButton(mounted.container));
      await flushReact();
      await mounted.rerender(null, blockedSettings);
      await mounted.rerender(profileWithNickname("initial"));

      const recoveredButton = saveButton(mounted.container);
      expect(recoveredButton.disabled).toBe(true);
      await act(async () => {
        dispatchSaveClick(recoveredButton);
      });
      expect(onSave).toHaveBeenCalledTimes(1);

      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      expect(recoveredButton.disabled).toBe(false);
    } finally {
      firstSave.resolve({ ok: true, message: "保存结果" });
      await flushReact();
      await mounted.unmount();
    }
  });

  test("renders success, failure, and no-op results from settled requests", async () => {
    const outcomes: CompanionUserProfileActionResult[] = [
      { ok: true, message: "保存成功结果" },
      { ok: false, message: "保存失败结果" },
      { ok: true, message: "没有新的变化结果" },
    ];

    for (const outcome of outcomes) {
      const pending = deferred<CompanionUserProfileActionResult>();
      const onSave = vi.fn(() => pending.promise);
      const mounted = await mountProfileSettings(onSave);
      try {
        dispatchSaveClick(saveButton(mounted.container));
        await flushReact();
        pending.resolve(outcome);
        await flushReact();
        expect(mounted.container.textContent).toContain(outcome.message);
      } finally {
        pending.resolve(outcome);
        await flushReact();
        await mounted.unmount();
      }
    }
  });
});
