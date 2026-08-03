import {
  createLocalRepository,
  type RepositoryDeletionGuard,
  sanitizeOutboxPayload,
  type LocalRepositoryEventInput,
} from "../storage/localRepository";
import { containsSensitiveCompanionText } from "./companionPrivacy";

export const COMPANION_MEMORY_STORAGE_KEY = "yuxin-companion-memory-v1";
export const COMPANION_MEMORY_SCHEMA_VERSION = 1;
export const MAX_COMPANION_MEMORY_CONTENT_CHARACTERS = 500;
export const MAX_COMPANION_MEMORY_EVIDENCE_CHARACTERS = 800;
export const MAX_COMPANION_MEMORY_ENTRIES = 200;
export const MAX_COMPANION_MEMORY_SEARCH_RESULTS = 3;
export const MIN_COMPANION_MEMORY_SEARCH_SCORE = 1.8;
const DELETED_MEMORY_TEXT = "（已删除）";

export type MemoryScope = "global" | `pet:${string}`;
export type MemoryType = "fact" | "relationship" | "episode" | "preference";
export type MemorySource = "explicit" | "confirmed";
export type MemoryStatus =
  | "active"
  | "disabled"
  | "superseded"
  | "deleted";

export type MemoryEntry = {
  id: string;
  scope: MemoryScope;
  type: MemoryType;
  content: string;
  source: MemorySource;
  evidence: string;
  sourceMessageId: string;
  confidence: number;
  createdAt: string;
  updatedAt: string;
  expiresAt: string | null;
  status: MemoryStatus;
  supersedesId: string | null;
  deletedAt: string | null;
};

export type MemoryEntryInput = {
  id?: string;
  scope: MemoryScope;
  type: MemoryType;
  content: string;
  source: MemorySource;
  evidence: string;
  sourceMessageId: string;
  confidence: number;
  createdAt?: string;
  updatedAt?: string;
  expiresAt?: string | null;
  status?: MemoryStatus;
  supersedesId?: string | null;
  deletedAt?: string | null;
};

export type MemoryEntryPatch = Partial<
  Pick<
    MemoryEntry,
    | "scope"
    | "type"
    | "content"
    | "evidence"
    | "confidence"
     | "expiresAt"
     | "status"
     | "supersedesId"
     | "deletedAt"
  >
>;

export type MemoryListOptions = {
  scope?: MemoryScope | readonly MemoryScope[];
  includeDeleted?: boolean;
};

export type MemorySearchOptions = {
  petId: string;
  now?: number;
  limit?: number;
  minScore?: number;
};

export type MemoryExportFormat = "json" | "markdown";

export type MemoryRepository = {
  list(options?: MemoryListOptions): MemoryEntry[];
  get(id: string): MemoryEntry | null;
  save(entry: MemoryEntryInput): MemoryEntry | null;
  update(id: string, patch: MemoryEntryPatch): MemoryEntry | null;
  disable(id: string): MemoryEntry | null;
  delete(id: string): MemoryEntry | null;
  search(query: string, options: MemorySearchOptions): MemoryEntry[];
  export(format?: MemoryExportFormat, options?: MemoryListOptions): string;
};

export type CompanionMemoryCandidate = {
  scope: MemoryScope;
  type: MemoryType;
  content: string;
  source: "explicit" | "inferred" | "confirmed";
  evidence: string;
  sourceMessageId: string;
  confidence: number;
  expiresAt: string | null;
  requiresConfirmation: boolean;
  confirmationReason: string;
  confirmed: boolean;
};

type CompanionMemoryState = {
  version: typeof COMPANION_MEMORY_SCHEMA_VERSION;
  entries: MemoryEntry[];
};

type StorageLike = Pick<Storage, "getItem" | "setItem">;

export type CompanionMemoryRepositoryOptions = {
  storage?: StorageLike;
  warn?: (message: string, error?: unknown) => void;
  now?: () => number;
  idGenerator?: () => string;
};

const EMPTY_COMPANION_MEMORY_STATE: CompanionMemoryState = {
  version: COMPANION_MEMORY_SCHEMA_VERSION,
  entries: [],
};

const MEMORY_TYPES: readonly MemoryType[] = [
  "fact",
  "relationship",
  "episode",
  "preference",
];
const MEMORY_SOURCES: readonly MemorySource[] = ["explicit", "confirmed"];
const MEMORY_STATUSES: readonly MemoryStatus[] = [
  "active",
  "disabled",
  "superseded",
  "deleted",
];
const MEMORY_SEARCH_STOP_WORDS = new Set([
  "我",
  "你",
  "他",
  "她",
  "它",
  "的",
  "了",
  "吗",
  "呢",
  "啊",
  "是",
  "有",
  "和",
  "跟",
  "请",
  "记住",
  "记得",
  "什么",
]);

function createFallbackStorage(): StorageLike {
  const fallbackStorage = new Map<string, string>();
  return {
    getItem: (key) => fallbackStorage.get(key) ?? null,
    setItem: (key, value) => {
      fallbackStorage.set(key, value);
    },
  };
}

function getDefaultStorage(): StorageLike {
  if (typeof window !== "undefined") {
    try {
      return window.localStorage;
    } catch {
      return createFallbackStorage();
    }
  }
  return createFallbackStorage();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isMemoryScope(value: unknown): value is MemoryScope {
  return (
    value === "global" ||
    (typeof value === "string" && /^pet:[^\s:]+$/.test(value))
  );
}

function isMemoryType(value: unknown): value is MemoryType {
  return typeof value === "string" && MEMORY_TYPES.includes(value as MemoryType);
}

function isMemorySource(value: unknown): value is MemorySource {
  return (
    typeof value === "string" && MEMORY_SOURCES.includes(value as MemorySource)
  );
}

function isMemoryStatus(value: unknown): value is MemoryStatus {
  return (
    typeof value === "string" && MEMORY_STATUSES.includes(value as MemoryStatus)
  );
}

function isIsoDate(value: unknown): value is string {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function isValidConfidence(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
}

function isSensitiveMemoryText(value: string): boolean {
  return containsSensitiveCompanionText(value);
}

export function containsSensitiveMemoryText(value: string): boolean {
  return isSensitiveMemoryText(value);
}

function isCompleteMemoryEntry(value: unknown): value is MemoryEntry {
  if (!isRecord(value)) return false;

  return (
    typeof value.id === "string" &&
    value.id.trim().length > 0 &&
    !isSensitiveMemoryText(value.id) &&
    isMemoryScope(value.scope) &&
    isMemoryType(value.type) &&
    typeof value.content === "string" &&
    value.content.trim().length > 0 &&
    Array.from(value.content).length <= MAX_COMPANION_MEMORY_CONTENT_CHARACTERS &&
    !isSensitiveMemoryText(value.content) &&
    isMemorySource(value.source) &&
    typeof value.evidence === "string" &&
    value.evidence.trim().length > 0 &&
    Array.from(value.evidence).length <= MAX_COMPANION_MEMORY_EVIDENCE_CHARACTERS &&
    !isSensitiveMemoryText(value.evidence) &&
    typeof value.sourceMessageId === "string" &&
    value.sourceMessageId.trim().length > 0 &&
    !isSensitiveMemoryText(value.sourceMessageId) &&
    isValidConfidence(value.confidence) &&
    isIsoDate(value.createdAt) &&
    isIsoDate(value.updatedAt) &&
    (value.expiresAt === null || isIsoDate(value.expiresAt)) &&
    isMemoryStatus(value.status) &&
    (value.supersedesId === null ||
      (typeof value.supersedesId === "string" &&
        !isSensitiveMemoryText(value.supersedesId))) &&
    (value.deletedAt === undefined || value.deletedAt === null || isIsoDate(value.deletedAt))
  );
}

function cloneEntry(entry: MemoryEntry): MemoryEntry {
  return { ...entry };
}

/**
 * Keep the local row shape compatible with schema v1 while removing the
 * original content, evidence, and message text as soon as a Memory is
 * deleted. The delete Event carries only the opaque entity id.
 */
function toMemoryTombstone(entry: MemoryEntry, deletedAt: string): MemoryEntry {
  return {
    ...entry,
    content: DELETED_MEMORY_TEXT,
    evidence: DELETED_MEMORY_TEXT,
    sourceMessageId: `deleted:${entry.id}`,
    confidence: 0,
    expiresAt: null,
    status: "deleted",
    supersedesId: null,
    updatedAt: deletedAt,
    deletedAt,
  };
}

function cloneState(state: CompanionMemoryState): CompanionMemoryState {
  return {
    version: state.version,
    entries: state.entries.map(cloneEntry),
  };
}

export function parseCompanionMemoryState(
  value: string | null,
  warn: (message: string, error?: unknown) => void = console.warn,
): CompanionMemoryState {
  if (!value) return cloneState(EMPTY_COMPANION_MEMORY_STATE);

  try {
    const parsed: unknown = JSON.parse(value);
    const normalizedEntries = isRecord(parsed) && Array.isArray(parsed.entries)
      ? parsed.entries.map((entry) =>
          isRecord(entry)
            ? {
                ...entry,
                deletedAt: entry.deletedAt
                  ?? (entry.status === "deleted" ? entry.updatedAt : null),
              }
            : entry,
        )
      : null;
    if (
      !isRecord(parsed) ||
      parsed.version !== COMPANION_MEMORY_SCHEMA_VERSION ||
      !normalizedEntries ||
      normalizedEntries.length > MAX_COMPANION_MEMORY_ENTRIES ||
      !normalizedEntries.every(isCompleteMemoryEntry)
    ) {
      throw new Error("Memory storage has an invalid schema");
    }

    return {
      version: COMPANION_MEMORY_SCHEMA_VERSION,
      entries: normalizedEntries.map((entry) => cloneEntry(entry)),
    };
  } catch (error) {
    warn("[companion-memory] Invalid or damaged local memory; using empty memory", error);
    return cloneState(EMPTY_COMPANION_MEMORY_STATE);
  }
}

function normalizeText(value: string): string {
  return value.replace(/\r\n?/g, "\n").replace(/\s+/g, " ").trim();
}

function createMemoryId(now: number, idGenerator: () => string): string {
  const generated = idGenerator().trim();
  return generated || `memory-${now.toString(36)}`;
}

function toIsoDate(value: string | undefined, fallback: number): string {
  if (value && isIsoDate(value)) return new Date(value).toISOString();
  return new Date(fallback).toISOString();
}

function normalizeMemoryEntry(
  input: MemoryEntryInput,
  now: number,
  idGenerator: () => string,
): MemoryEntry | null {
  const content = normalizeText(input.content);
  const evidence = normalizeText(input.evidence);
  const id = input.id?.trim() || createMemoryId(now, idGenerator);
  if (
    !id ||
    isSensitiveMemoryText(id) ||
    !isMemoryScope(input.scope) ||
    !isMemoryType(input.type) ||
    !isMemorySource(input.source) ||
    !isMemoryStatus(input.status ?? "active") ||
    !content ||
    !evidence ||
    Array.from(content).length > MAX_COMPANION_MEMORY_CONTENT_CHARACTERS ||
    Array.from(evidence).length > MAX_COMPANION_MEMORY_EVIDENCE_CHARACTERS ||
    isSensitiveMemoryText(content) ||
    isSensitiveMemoryText(evidence) ||
    typeof input.sourceMessageId !== "string" ||
    !input.sourceMessageId.trim() ||
    isSensitiveMemoryText(input.sourceMessageId) ||
    !isValidConfidence(input.confidence) ||
    (input.expiresAt !== undefined &&
      input.expiresAt !== null &&
      !isIsoDate(input.expiresAt)) ||
    (input.supersedesId !== undefined &&
      input.supersedesId !== null &&
      (typeof input.supersedesId !== "string" ||
        isSensitiveMemoryText(input.supersedesId)))
  ) {
    return null;
  }

  const createdAt = toIsoDate(input.createdAt, now);
  const updatedAt = toIsoDate(input.updatedAt, now);
  return {
    id,
    scope: input.scope,
    type: input.type,
    content,
    source: input.source,
    evidence,
    sourceMessageId: input.sourceMessageId.trim(),
    confidence: input.confidence,
    createdAt,
    updatedAt,
    expiresAt:
      input.expiresAt === undefined || input.expiresAt === null
        ? null
        : new Date(input.expiresAt).toISOString(),
    status: input.status ?? "active",
    supersedesId: input.supersedesId?.trim() || null,
    deletedAt:
      input.deletedAt === undefined || input.deletedAt === null
        ? input.status === "deleted" ? updatedAt : null
        : new Date(input.deletedAt).toISOString(),
  };
}

function scopeMatches(
  scope: MemoryScope,
  requested: MemoryScope | readonly MemoryScope[] | undefined,
): boolean {
  if (!requested) return true;
  return Array.isArray(requested)
    ? requested.includes(scope)
    : requested === scope;
}

function isVisibleToPet(scope: MemoryScope, petId: string): boolean {
  const normalizedPetId = petId.trim();
  return Boolean(normalizedPetId) &&
    (scope === "global" || scope === `pet:${normalizedPetId}`);
}

function searchScopePriority(entry: MemoryEntry, petId: string): number {
  if (entry.scope === `pet:${petId}` && entry.type === "relationship") return 2;
  if (entry.scope === `pet:${petId}`) return 1;
  return 0;
}

function isActiveAt(entry: MemoryEntry, now: number): boolean {
  return (
    entry.status === "active" &&
    (entry.expiresAt === null || Date.parse(entry.expiresAt) > now)
  );
}

function searchTerms(value: string): string[] {
  const terms = new Set<string>();
  const normalized = normalizeText(value).toLocaleLowerCase();
  const runs = normalized.match(/[a-z0-9]+|[\u3400-\u9fff]+/gi) ?? [];

  for (const run of runs) {
    if (/^[a-z0-9]+$/i.test(run)) {
      if (run.length >= 2 && !MEMORY_SEARCH_STOP_WORDS.has(run)) terms.add(run);
      continue;
    }

    if (run.length === 1) {
      if (!MEMORY_SEARCH_STOP_WORDS.has(run)) terms.add(run);
      continue;
    }

    if (run.length <= 8 && !MEMORY_SEARCH_STOP_WORDS.has(run)) terms.add(run);
    for (let index = 0; index < run.length - 1; index += 1) {
      const bigram = run.slice(index, index + 2);
      if (!MEMORY_SEARCH_STOP_WORDS.has(bigram)) terms.add(bigram);
    }
  }

  return [...terms];
}

function scoreMemory(entry: MemoryEntry, query: string, now: number): number {
  const normalizedQuery = normalizeText(query).toLocaleLowerCase();
  const content = normalizeText(entry.content).toLocaleLowerCase();
  const terms = searchTerms(normalizedQuery);
  if (!terms.length || !content) return 0;

  const matchingTerms = terms.filter((term) => content.includes(term));
  if (!matchingTerms.length) return 0;

  const phraseScore =
    normalizedQuery.length >= 2 && content.includes(normalizedQuery) ? 4 : 0;
  const coverageScore = matchingTerms.length / terms.length;
  const lexicalScore = phraseScore + matchingTerms.length * 1.2 + coverageScore;
  const confidenceScore = entry.confidence * 1.5;
  const ageMs = Math.max(0, now - Date.parse(entry.updatedAt));
  const recencyScore = Math.max(0, 0.8 - ageMs / (365 * 24 * 60 * 60 * 1000));
  return lexicalScore + confidenceScore + recencyScore;
}

function defaultIdGenerator(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;
}

export function createCompanionMemoryRepository(
  options: CompanionMemoryRepositoryOptions = {},
): MemoryRepository {
  const storage = options.storage ?? getDefaultStorage();
  const warn = options.warn ?? console.warn;
  const now = options.now ?? Date.now;
  const idGenerator = options.idGenerator ?? defaultIdGenerator;
  const localRepository = createLocalRepository({
    storage,
    warn,
    now,
    idGenerator,
  });

  const applyDeletionGuards = (state: CompanionMemoryState): CompanionMemoryState => {
    const guards = localRepository
      .listDeletionGuards()
      .filter((guard) => guard.storageKey === COMPANION_MEMORY_STORAGE_KEY && guard.entityType === "memory");
    if (!guards.length) return state;
    const guardsById = new Map(guards.map((guard) => [guard.entityId, guard]));
    return {
      ...state,
      entries: state.entries.map((entry) => {
        const guard: RepositoryDeletionGuard | undefined = guardsById.get(entry.id);
        if (!guard || entry.status === "deleted") return entry;
        // A later explicit local save is allowed to replace a deleted id. An
        // unchanged row from a partially recovered transaction is not.
        if (Date.parse(entry.updatedAt) > Date.parse(guard.deletedAt)) return entry;
        return toMemoryTombstone(entry, guard.deletedAt);
      }),
    };
  };

  const readState = (): CompanionMemoryState => {
    try {
      const entity = localRepository.readEntity<CompanionMemoryState>(COMPANION_MEMORY_STORAGE_KEY);
      if (
        entity
        && isRecord(entity.data)
        && entity.data.version === COMPANION_MEMORY_SCHEMA_VERSION
        && Array.isArray(entity.data.entries)
      ) {
        return applyDeletionGuards(parseCompanionMemoryState(JSON.stringify(entity.data), warn));
      }
      return applyDeletionGuards(parseCompanionMemoryState(
        storage.getItem(COMPANION_MEMORY_STORAGE_KEY),
        warn,
      ));
    } catch (error) {
      warn("[companion-memory] Failed to read local memory; using empty memory", error);
      return cloneState(EMPTY_COMPANION_MEMORY_STATE);
    }
  };

  const writeState = (state: CompanionMemoryState): boolean => {
    const previous = readState();
    if (JSON.stringify(previous) === JSON.stringify(state)) return true;
    const nowIso = new Date(now()).toISOString();
    const previousEntries = new Map(previous.entries.map((entry) => [entry.id, entry]));
    const nextEntries = new Map(state.entries.map((entry) => [entry.id, entry]));
    const events: LocalRepositoryEventInput[] = [];
    for (const id of new Set([...previousEntries.keys(), ...nextEntries.keys()])) {
      const before = previousEntries.get(id);
      const after = nextEntries.get(id);
      if (JSON.stringify(before) === JSON.stringify(after)) continue;
      const isDeleted = !after || after.status === "deleted";
      const deletedAt = after?.deletedAt ?? before?.deletedAt ?? nowIso;
      events.push({
        entityType: "memory",
        entityId: id,
        operation: isDeleted ? "delete" : "upsert",
        schemaVersion: COMPANION_MEMORY_SCHEMA_VERSION,
        updatedAt: after?.updatedAt ?? deletedAt,
        deletedAt: isDeleted ? deletedAt : null,
        payload: isDeleted
          ? { id }
          : sanitizeOutboxPayload(after),
      });
    }
    const result = localRepository.writeEntity({
      storageKey: COMPANION_MEMORY_STORAGE_KEY,
      entityType: "memory-state",
      entityId: "memory-collection",
      schemaVersion: COMPANION_MEMORY_SCHEMA_VERSION,
      data: state,
      updatedAt: nowIso,
      deletedAt: null,
      events,
    });
    if (!result.ok) {
      warn("[companion-memory] Failed to write local memory and outbox", result.error);
    }
    return result.ok;
  };

  const list = (listOptions: MemoryListOptions = {}): MemoryEntry[] => {
    const state = readState();
    return state.entries
      .filter((entry) => listOptions.includeDeleted || entry.status !== "deleted")
      .filter((entry) => scopeMatches(entry.scope, listOptions.scope))
      .sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt))
      .map(cloneEntry);
  };

  const updateEntry = (id: string, patch: MemoryEntryPatch): MemoryEntry | null => {
    const state = readState();
    const existing = state.entries.find((entry) => entry.id === id);
    if (!existing || existing.status === "deleted") return null;

    const currentTime = now();
    const normalized = normalizeMemoryEntry(
      {
        ...existing,
        ...patch,
        id: existing.id,
        createdAt: existing.createdAt,
        updatedAt: new Date(currentTime).toISOString(),
      },
      currentTime,
      idGenerator,
    );
    if (!normalized) {
      warn("[companion-memory] Rejected invalid or sensitive memory update");
      return null;
    }

    const updated = normalized.status === "deleted"
      ? toMemoryTombstone(normalized, new Date(currentTime).toISOString())
      : normalized;

    const entries = state.entries.map((entry) =>
      entry.id === id ? updated : entry,
    );
    if (!writeState({ version: COMPANION_MEMORY_SCHEMA_VERSION, entries })) {
      return null;
    }
    return cloneEntry(updated);
  };

  return {
    list,

    get(id) {
      const entry = readState().entries.find((item) => item.id === id);
      return entry ? cloneEntry(entry) : null;
    },

    save(input) {
      const currentTime = now();
      const normalizedEntry = normalizeMemoryEntry(input, currentTime, idGenerator);
      if (!normalizedEntry) {
        warn("[companion-memory] Rejected invalid or sensitive memory entry");
        return null;
      }
      const normalized = normalizedEntry.status === "deleted"
        ? toMemoryTombstone(normalizedEntry, new Date(currentTime).toISOString())
        : normalizedEntry;

      const state = readState();
      const entries = [
        ...state.entries.filter((entry) => entry.id !== normalized.id),
        normalized,
      ];
      if (entries.length > MAX_COMPANION_MEMORY_ENTRIES) {
        warn("[companion-memory] Memory entry limit reached; entry was not saved");
        return null;
      }
      if (!writeState({ version: COMPANION_MEMORY_SCHEMA_VERSION, entries })) {
        return null;
      }
      return cloneEntry(normalized);
    },

    update: updateEntry,

    disable(id) {
      return updateEntry(id, { status: "disabled" });
    },

    delete(id) {
      return updateEntry(id, {
        status: "deleted",
        deletedAt: new Date(now()).toISOString(),
      });
    },

    search(query, searchOptions) {
      const normalizedQuery = normalizeText(query);
      const petId = searchOptions.petId.trim();
      if (!normalizedQuery || !petId || petId === "unknown") return [];

      const currentTime = searchOptions.now ?? now();
      const limit = Math.max(
        0,
        Math.min(
          MAX_COMPANION_MEMORY_SEARCH_RESULTS,
          Math.floor(searchOptions.limit ?? MAX_COMPANION_MEMORY_SEARCH_RESULTS),
        ),
      );
      const threshold = searchOptions.minScore ?? MIN_COMPANION_MEMORY_SEARCH_SCORE;
      if (!limit) return [];

      return readState()
        .entries.map((entry) => ({
          entry,
          scopePriority: searchScopePriority(entry, petId),
          score: isVisibleToPet(entry.scope, petId) && isActiveAt(entry, currentTime)
            ? scoreMemory(entry, normalizedQuery, currentTime)
            : 0,
        }))
        .filter(({ score }) => score >= threshold)
        .sort((left, right) =>
          right.scopePriority - left.scopePriority ||
          right.score - left.score ||
          Date.parse(right.entry.updatedAt) - Date.parse(left.entry.updatedAt),
        )
        .slice(0, limit)
        .map(({ entry }) => cloneEntry(entry));
    },

    export(format = "json", exportOptions = {}) {
      const entries = list(exportOptions);
      if (format === "markdown") {
        const lines = [
          "# 愈心桌宠已保存 Memory",
          "",
          "以下内容是本机导出的 Memory 条目，不包含完整聊天记录。",
          "",
        ];
        if (!entries.length) lines.push("暂无 Memory。", "");
        for (const entry of entries) {
          lines.push(
            `## ${entry.content}`,
            `- 类型：${entry.type}`,
            `- 作用域：${entry.scope}`,
            `- 来源：${entry.source}`,
            `- 来源消息：${entry.sourceMessageId}`,
            `- 证据：${entry.evidence}`,
            `- 状态：${entry.status}`,
            `- 置信度：${entry.confidence}`,
            `- 更新时间：${entry.updatedAt}`,
            `- 过期时间：${entry.expiresAt ?? "不设置"}`,
            "",
          );
        }
        return lines.join("\n");
      }

      return JSON.stringify(
        {
          version: COMPANION_MEMORY_SCHEMA_VERSION,
          exportedAt: new Date(now()).toISOString(),
          entries,
        },
        null,
        2,
      );
    },
  };
}

function extractRememberedContent(input: string): {
  content: string;
  type: MemoryType;
  scopeKind: "global" | "pet";
} | null {
  const normalized = normalizeText(input)
    .replace(/^[：:，,、\s]+/, "")
    .replace(/[。！？!]+$/, "")
    .trim();
  if (!normalized) return null;

  if (/^(?:我和你|我们)/u.test(normalized)) {
    return { content: normalized, type: "relationship", scopeKind: "pet" };
  }
  if (/^我(?:喜欢|不喜欢|习惯|通常)/u.test(normalized)) {
    return {
      content: `用户${normalized.slice(1)}`,
      type: "preference",
      scopeKind: "global",
    };
  }
  if (/^(?:我的昵称是|我叫)/u.test(normalized)) {
    return { content: `用户${normalized}`, type: "fact", scopeKind: "global" };
  }

  return null;
}

export function extractCompanionMemoryCandidate(
  text: string,
  sourceMessageId: string,
  petId: string,
): CompanionMemoryCandidate | null {
  const input = normalizeText(text);
  const normalizedPetId = petId.trim();
  if (
    !input ||
    !sourceMessageId.trim() ||
    !normalizedPetId ||
    isSensitiveMemoryText(input) ||
    isSensitiveMemoryText(sourceMessageId)
  ) return null;

  const rememberMatch = input.match(
    /^(?:(?:请|请你|帮我)\s*)?(?:务必\s*)?(?:记住|记下)(?:这个|这件事|一下)?(?:[：:，,、\s]*)?(.+)$/u,
  );
  const rememberAfterMatch = input.match(
    /^(.+?)[，,、\s]+(?:(?:请|请你|帮我)\s*)?(?:务必\s*)?(?:记住|记下)(?:这个|这件事|一下)?[。！？!?]*$/u,
  );
  const rememberedText = rememberMatch?.[1] ?? rememberAfterMatch?.[1] ?? "";
  if (!rememberedText) return null;

  const extracted = extractRememberedContent(rememberedText);
  if (!extracted || isSensitiveMemoryText(extracted.content)) return null;
  if (/提醒|待办|任务|明天|后天|下周|可能|也许|假设|玩笑|开玩笑/u.test(extracted.content)) {
    return null;
  }

  return {
    scope: extracted.scopeKind === "pet" ? `pet:${normalizedPetId}` : "global",
    type: extracted.type,
    content: extracted.content,
    source: "explicit",
    evidence: input,
    sourceMessageId: sourceMessageId.trim(),
    confidence: 0.98,
    expiresAt: null,
    requiresConfirmation: false,
    confirmationReason:
      "用户使用了明确的“记住”或称呼表达，可直接保存；仍可在设置中编辑、禁用或删除。",
    confirmed: true,
  };
}

export function confirmCompanionMemoryCandidate(
  candidate: CompanionMemoryCandidate,
): CompanionMemoryCandidate {
  return {
    ...candidate,
    source: "confirmed",
    requiresConfirmation: false,
    confirmationReason: "用户已明确确认这条 Memory。",
    confirmed: true,
  };
}

export function saveCompanionMemoryCandidate(
  repository: MemoryRepository,
  candidate: CompanionMemoryCandidate,
): MemoryEntry | null {
  if (!candidate.confirmed || candidate.requiresConfirmation) return null;
  return repository.save({
    scope: candidate.scope,
    type: candidate.type,
    content: candidate.content,
    source: candidate.source === "explicit" ? "explicit" : "confirmed",
    evidence: candidate.evidence,
    sourceMessageId: candidate.sourceMessageId,
    confidence: candidate.confidence,
    expiresAt: candidate.expiresAt,
    status: "active",
    supersedesId: null,
  });
}

export function searchCompanionMemorySafely(
  repository: MemoryRepository,
  query: string,
  options: MemorySearchOptions,
  warn: (message: string, error?: unknown) => void = console.warn,
): MemoryEntry[] {
  try {
    return repository.search(query, options);
  } catch (error) {
    warn("[companion-memory] Search failed; continuing without memory context", error);
    return [];
  }
}
