import { describe, expect, test, vi } from "vitest";
import {
  BUILT_IN_LETTERS,
  EMPTY_MAILBOX_STATE,
  MAILBOX_STORAGE_KEY,
  WELCOME_LETTER_ID,
  canDeleteReadLetters,
  deleteReadLetters,
  getUnreadCount,
  getVisibleLetters,
  isLetterRead,
  markAllLettersRead,
  markLetterRead,
  parseMailboxState,
  readMailboxState,
  shouldShowFirstUseLetter,
  writeMailboxState,
  type MailboxState,
  type MailboxStorage,
  type PlatformLetter,
} from "./mailbox";

const updateLetter: PlatformLetter = {
  id: "update-0.1.3",
  title: "0.1.3 更新公告",
  sender: "望星科技 × 知了",
  publishedAt: "2026-06-20",
  type: "update",
  paragraphs: ["更新内容。"],
  permanent: false,
};

function createStorage(initialValue: string | null = null): MailboxStorage {
  let value = initialValue;

  return {
    getItem: vi.fn(() => value),
    setItem: vi.fn((_key, nextValue) => {
      value = nextValue;
    }),
  };
}

describe("platform mailbox", () => {
  test("ships the approved permanent welcome letter", () => {
    expect(MAILBOX_STORAGE_KEY).toBe("yuxin-mailbox-state-v1");
    expect(WELCOME_LETTER_ID).toBe("welcome-first-meeting");
    expect(BUILT_IN_LETTERS).toEqual([
      {
        id: WELCOME_LETTER_ID,
        title: "致初次相遇的您",
        sender: "望星科技 × 知了",
        publishedAt: "2026-06-19",
        type: "welcome",
        permanent: true,
        paragraphs: [
          "亲爱的用户：",
          "您好！很高兴您可以使用我们的产品。",
          "城市的霓虹伴随着繁华，但是繁复的灯光总是晃眼的，如果您累了，不妨与我们的桌宠嬉戏一下。或许他/她/它不能给您缓解身体的疲劳，但是我们希望，您在某一个瞬间看到我们桌宠的时候，也会噗嗤一笑。所以，来领养一只桌宠吧！希望我们的桌宠能够治愈您的心灵。",
          "生活很累，但也很甜，希望您身体健康，万事如意，平安喜乐。",
        ],
      },
    ]);
  });

  test("keeps first use active until the welcome letter is opened", () => {
    expect(shouldShowFirstUseLetter(EMPTY_MAILBOX_STATE)).toBe(true);

    const readState = markLetterRead(EMPTY_MAILBOX_STATE, WELCOME_LETTER_ID);

    expect(isLetterRead(readState, WELCOME_LETTER_ID)).toBe(true);
    expect(shouldShowFirstUseLetter(readState)).toBe(false);
  });

  test("marks all visible letters read without duplicating ids", () => {
    const letters = [...BUILT_IN_LETTERS, updateLetter];
    const result = markAllLettersRead(
      { readLetterIds: [WELCOME_LETTER_ID], deletedLetterIds: [] },
      letters,
    );

    expect(result.readLetterIds).toEqual([WELCOME_LETTER_ID, updateLetter.id]);
    expect(getUnreadCount(letters, result)).toBe(0);
  });

  test("deletes only read non-permanent letters", () => {
    const letters = [...BUILT_IN_LETTERS, updateLetter];
    const state: MailboxState = {
      readLetterIds: [WELCOME_LETTER_ID, updateLetter.id],
      deletedLetterIds: [],
    };
    const result = deleteReadLetters(state, letters);

    expect(result.deletedLetterIds).toEqual([updateLetter.id]);
    expect(getVisibleLetters(letters, result)).toEqual(BUILT_IN_LETTERS);
    expect(canDeleteReadLetters(result, letters)).toBe(false);
  });

  test("repairs invalid storage and removes permanent ids from deleted state", () => {
    expect(parseMailboxState("not-json")).toEqual(EMPTY_MAILBOX_STATE);
    expect(
      parseMailboxState(
        JSON.stringify({
          readLetterIds: [WELCOME_LETTER_ID, 3, WELCOME_LETTER_ID],
          deletedLetterIds: [WELCOME_LETTER_ID, updateLetter.id, null],
        }),
      ),
    ).toEqual({
      readLetterIds: [WELCOME_LETTER_ID],
      deletedLetterIds: [updateLetter.id],
    });
  });

  test("reads and writes through the versioned storage key", () => {
    const storage = createStorage(
      JSON.stringify({
        readLetterIds: [WELCOME_LETTER_ID],
        deletedLetterIds: [],
      }),
    );
    const warn = vi.fn();
    const state = readMailboxState(storage, warn);

    expect(storage.getItem).toHaveBeenCalledWith(MAILBOX_STORAGE_KEY);
    expect(state.readLetterIds).toEqual([WELCOME_LETTER_ID]);
    expect(writeMailboxState(state, storage, warn)).toBe(true);
    expect(storage.setItem).toHaveBeenCalledWith(
      MAILBOX_STORAGE_KEY,
      JSON.stringify(state),
    );
    expect(warn).not.toHaveBeenCalled();
  });

  test("falls back in memory when storage throws", () => {
    const storage: MailboxStorage = {
      getItem: vi.fn(() => {
        throw new Error("blocked");
      }),
      setItem: vi.fn(() => {
        throw new Error("blocked");
      }),
    };
    const warn = vi.fn();

    expect(readMailboxState(storage, warn)).toEqual(EMPTY_MAILBOX_STATE);
    expect(writeMailboxState(EMPTY_MAILBOX_STATE, storage, warn)).toBe(false);
    expect(warn).toHaveBeenCalledTimes(2);
  });
});
