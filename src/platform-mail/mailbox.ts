export type PlatformLetter = {
  id: string;
  title: string;
  sender: string;
  publishedAt: string;
  type: "welcome" | "update";
  paragraphs: string[];
  permanent: boolean;
};

export type MailboxState = {
  readLetterIds: string[];
  deletedLetterIds: string[];
};

export type MailboxStorage = Pick<Storage, "getItem" | "setItem">;
export type MailboxWarning = (message: string, error?: unknown) => void;

export const MAILBOX_STORAGE_KEY = "yuxin-mailbox-state-v1";
export const WELCOME_LETTER_ID = "welcome-first-meeting";
export const EMPTY_MAILBOX_STATE: MailboxState = {
  readLetterIds: [],
  deletedLetterIds: [],
};

export const BUILT_IN_LETTERS: PlatformLetter[] = [
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
];

function uniqueStrings(value: unknown): string[] {
  if (!Array.isArray(value)) return [];

  return [
    ...new Set(value.filter((item): item is string => typeof item === "string")),
  ];
}

function permanentLetterIds(): Set<string> {
  return new Set(
    BUILT_IN_LETTERS.filter((letter) => letter.permanent).map(
      (letter) => letter.id,
    ),
  );
}

function normalizeMailboxState(value: unknown): MailboxState {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return { ...EMPTY_MAILBOX_STATE };
  }

  const record = value as Record<string, unknown>;
  const permanentIds = permanentLetterIds();

  return {
    readLetterIds: uniqueStrings(record.readLetterIds),
    deletedLetterIds: uniqueStrings(record.deletedLetterIds).filter(
      (id) => !permanentIds.has(id),
    ),
  };
}

export function parseMailboxState(raw: string | null): MailboxState {
  if (!raw) return { ...EMPTY_MAILBOX_STATE };

  try {
    return normalizeMailboxState(JSON.parse(raw));
  } catch {
    return { ...EMPTY_MAILBOX_STATE };
  }
}

function browserStorage(): MailboxStorage | null {
  if (typeof window === "undefined") return null;

  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function readMailboxState(
  storage: MailboxStorage | null = browserStorage(),
  warn: MailboxWarning = console.warn,
): MailboxState {
  if (!storage) return { ...EMPTY_MAILBOX_STATE };

  try {
    return parseMailboxState(storage.getItem(MAILBOX_STORAGE_KEY));
  } catch (error) {
    warn("[mailbox] Failed to read mailbox state", error);
    return { ...EMPTY_MAILBOX_STATE };
  }
}

export function writeMailboxState(
  state: MailboxState,
  storage: MailboxStorage | null = browserStorage(),
  warn: MailboxWarning = console.warn,
): boolean {
  if (!storage) return false;

  try {
    storage.setItem(MAILBOX_STORAGE_KEY, JSON.stringify(normalizeMailboxState(state)));
    return true;
  } catch (error) {
    warn("[mailbox] Failed to write mailbox state", error);
    return false;
  }
}

export function isLetterRead(state: MailboxState, letterId: string): boolean {
  return state.readLetterIds.includes(letterId);
}

export function shouldShowFirstUseLetter(state: MailboxState): boolean {
  return !isLetterRead(state, WELCOME_LETTER_ID);
}

export function markLetterRead(
  state: MailboxState,
  letterId: string,
): MailboxState {
  if (state.readLetterIds.includes(letterId)) return state;

  return {
    ...state,
    readLetterIds: [...state.readLetterIds, letterId],
  };
}

export function getVisibleLetters(
  letters: PlatformLetter[],
  state: MailboxState,
): PlatformLetter[] {
  const deletedIds = new Set(state.deletedLetterIds);
  return letters.filter((letter) => letter.permanent || !deletedIds.has(letter.id));
}

export function getUnreadCount(
  letters: PlatformLetter[],
  state: MailboxState,
): number {
  return getVisibleLetters(letters, state).filter(
    (letter) => !isLetterRead(state, letter.id),
  ).length;
}

export function markAllLettersRead(
  state: MailboxState,
  letters: PlatformLetter[],
): MailboxState {
  return getVisibleLetters(letters, state).reduce(
    (nextState, letter) => markLetterRead(nextState, letter.id),
    state,
  );
}

export function deleteReadLetters(
  state: MailboxState,
  letters: PlatformLetter[],
): MailboxState {
  const deletableIds = letters
    .filter(
      (letter) =>
        !letter.permanent &&
        isLetterRead(state, letter.id) &&
        !state.deletedLetterIds.includes(letter.id),
    )
    .map((letter) => letter.id);

  if (deletableIds.length === 0) return state;

  return {
    ...state,
    deletedLetterIds: [...state.deletedLetterIds, ...deletableIds],
  };
}

export function canDeleteReadLetters(
  state: MailboxState,
  letters: PlatformLetter[],
): boolean {
  return letters.some(
    (letter) =>
      !letter.permanent &&
      isLetterRead(state, letter.id) &&
      !state.deletedLetterIds.includes(letter.id),
  );
}
