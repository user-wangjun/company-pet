import {
  createCompanionMemoryRepository,
  containsSensitiveMemoryText,
  type MemoryEntry,
  type MemoryEntryInput,
  type MemoryRepository,
} from "./companionMemory";
import {
  extractCompanionMemoryCandidate,
  type CompanionMemoryCandidate,
} from "./companionMemory";
import { containsSensitiveCompanionText } from "./companionPrivacy";
import { normalizeCompanionMemoryCandidate } from "./companionModelCodec";
import type {
  CompanionInput,
  CompanionMemoryConfirmationProof,
  CompanionMemoryConfirmationVerifier,
  CompanionMemoryService,
  MemoryCandidate,
  MemoryCandidateDecision,
  MemoryPolicyResult,
  MemoryScope,
  MemoryType,
} from "./companionHarnessTypes";

const MEMORY_POLICY_MAX_TEXT_LENGTH = 600;

export type CompanionMemoryAuthorization =
  | {
      status: "authorized";
      source: "explicit" | "confirmed";
      evidence: string;
    }
  | {
      status: "confirmation_required";
      errorCode: "explicit-proof-missing" | "confirmation-proof-missing";
    }
  | {
      status: "rejected";
      errorCode: string;
    };

export type CompanionMemoryPolicyOptions = {
  repository: MemoryRepository;
  now?: () => number;
  confirmationVerifier?: CompanionMemoryConfirmationVerifier;
};

export type CompanionMemoryDecisionContext = {
  input: CompanionInput;
  candidate: MemoryCandidate;
  index: number;
  repository: MemoryRepository;
  now: number;
  signal: AbortSignal;
  confirmationVerifier?: CompanionMemoryConfirmationVerifier;
};

export type CompanionMemoryDecision =
  | {
      status: "inserted" | "superseded" | "updated" | "duplicate" | "expired" | "ignored" | "failed" | "cancelled";
      candidate: MemoryCandidate;
      index: number;
      scope: MemoryScope;
      type: MemoryType;
      resourceId?: string;
      supersedesId?: string;
      errorCode?: string;
    }
  | {
      status: "confirmation_required" | "rejected";
      candidate: MemoryCandidate | null;
      index: number;
      scope?: MemoryScope;
      type?: MemoryType;
      resourceId?: string;
      supersedesId?: string;
      errorCode: string;
    };

function normalizeText(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/\r\n?/gu, "\n")
    .replace(/\s+/gu, " ")
    .trim();
}

/**
 * Comparison normalization is intentionally conservative: it handles case,
 * whitespace, full/half-width punctuation and sentence-final punctuation, but
 * leaves semantic words such as 不喜欢 intact.
 */
export function normalizeCompanionMemoryComparisonText(value: string): string {
  return normalizeText(value)
    .toLocaleLowerCase()
    // NFKC above folds full-width punctuation. Only remove punctuation at
    // the sentence boundary; internal punctuation can carry meaning and
    // must not be erased by near-duplicate matching.
    .replace(/[\p{P}\p{S}]+$/gu, "")
    .replace(/\s+/gu, "");
}

const SHA256_K = [
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
  0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
  0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
  0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
  0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
  0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
  0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
] as const;

const SHA256_INITIAL_STATE = [
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
  0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
] as const;

function rotateRight(value: number, amount: number): number {
  return (value >>> amount) | (value << (32 - amount));
}

/**
 * Synchronous, platform-independent SHA-256 for opaque local identities.
 * TextEncoder and typed arrays are Web APIs available in browsers and Tauri;
 * this deliberately does not depend on Node's crypto module.
 */
function sha256Hex(value: string): string {
  const bytes = new TextEncoder().encode(value);
  const paddedLength = Math.ceil((bytes.length + 9) / 64) * 64;
  const padded = new Uint8Array(paddedLength);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const bitLength = bytes.length * 8;
  const view = new DataView(padded.buffer);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x1_0000_0000));
  view.setUint32(paddedLength - 4, bitLength >>> 0);

  const state: number[] = [...SHA256_INITIAL_STATE];
  const words = new Uint32Array(64);
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let index = 0; index < 16; index += 1) {
      words[index] = view.getUint32(offset + index * 4);
    }
    for (let index = 16; index < 64; index += 1) {
      const first = words[index - 15];
      const second = words[index - 2];
      const sigma0 = rotateRight(first, 7) ^ rotateRight(first, 18) ^ (first >>> 3);
      const sigma1 = rotateRight(second, 17) ^ rotateRight(second, 19) ^ (second >>> 10);
      words[index] = (words[index - 16] + sigma0 + words[index - 7] + sigma1) >>> 0;
    }

    let [a, b, c, d, e, f, g, h] = state;
    for (let index = 0; index < 64; index += 1) {
      const bigSigma1 = rotateRight(e, 6) ^ rotateRight(e, 11) ^ rotateRight(e, 25);
      const choose = (e & f) ^ (~e & g);
      const first = (h + bigSigma1 + choose + SHA256_K[index] + words[index]) >>> 0;
      const bigSigma0 = rotateRight(a, 2) ^ rotateRight(a, 13) ^ rotateRight(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const second = (bigSigma0 + majority) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + first) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (first + second) >>> 0;
    }
    state[0] = (state[0] + a) >>> 0;
    state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0;
    state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0;
    state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0;
    state[7] = (state[7] + h) >>> 0;
  }

  return state.map((word) => word.toString(16).padStart(8, "0")).join("");
}

function formatOpaqueDigest(value: string): string {
  return value.match(/.{1,8}/gu)?.join("-") ?? value;
}

function candidateIdentityFingerprint(candidate: MemoryCandidate): string {
  return [
    "companion-memory-candidate-v2",
    candidate.scope,
    candidate.type,
    candidate.category,
    candidate.lifetime,
    candidate.expiresAt ?? "null",
    normalizeCompanionMemoryComparisonText(candidate.content),
  ].join("\u001f");
}

/** Does not expose candidate content; only a deterministic opaque id is returned. */
export function getCompanionMemoryCandidateId(candidate: MemoryCandidate): string {
  return `memory-candidate-${formatOpaqueDigest(sha256Hex(candidateIdentityFingerprint(candidate)))}`;
}

/**
 * Entry identity is separate from confirmation identity. A correction gets a
 * new revision digest tied to the superseded row, while an ordinary retry of
 * the same candidate keeps the same root revision and is deduplicated.
 */
export function getCompanionMemoryRevisionId(
  candidate: MemoryCandidate,
  supersedesId: string | null = null,
): string {
  const seed = [
    "companion-memory-revision-v1",
    candidateIdentityFingerprint(candidate),
    supersedesId ?? "root",
  ].join("\u001f");
  return `memory-revision-${formatOpaqueDigest(sha256Hex(seed))}`;
}

function canonicalCandidate(
  input: CompanionInput,
  candidate: MemoryCandidate | CompanionMemoryCandidate,
): MemoryCandidate | null {
  const { confirmationReason: _confirmationReason, ...wireCandidate } = candidate as CompanionMemoryCandidate;
  return normalizeCompanionMemoryCandidate(wireCandidate, {
    mode: "json_object",
    // A confirmation proof may deliberately carry the original candidate's
    // source message id; ordinary model candidates must match the current
    // input exactly and are already enforced by the Codec.
    sourceMessageId: candidate.confirmationStatus === "confirmed"
      && candidate.sourceMessageId !== input.sourceMessageId
      ? candidate.sourceMessageId
      : input.sourceMessageId,
    petId: input.petId,
  });
}

function candidateNow(input: CompanionInput): number | null {
  const parsed = Date.parse(input.currentTime);
  return Number.isFinite(parsed) ? parsed : null;
}

function localExplicitCandidate(input: CompanionInput): CompanionMemoryCandidate | null {
  return extractCompanionMemoryCandidate(
    input.message,
    input.sourceMessageId,
    input.petId,
  );
}

function sameExplicitEvidence(
  candidate: MemoryCandidate,
  explicit: CompanionMemoryCandidate,
): boolean {
  return candidate.sourceMessageId === explicit.sourceMessageId
    && candidate.scope === explicit.scope
    && candidate.type === explicit.type
    && candidate.category === explicit.category
    && candidate.lifetime === explicit.lifetime
    && candidate.expiresAt === explicit.expiresAt
    && candidate.confirmationStatus !== "requires_confirmation"
    && normalizeCompanionMemoryComparisonText(candidate.content)
      === normalizeCompanionMemoryComparisonText(explicit.content);
}

function validConfirmationProof(
  proof: CompanionMemoryConfirmationProof | null,
  input: CompanionInput,
  candidate: MemoryCandidate,
): boolean {
  return proof !== null
    && proof.status === "confirmed"
    && proof.candidateId === getCompanionMemoryCandidateId(candidate)
    && proof.sourceMessageId === candidate.sourceMessageId
    && proof.confirmationMessageId === input.sourceMessageId
    && proof.sessionId === input.sessionId
    && proof.petId === input.petId;
}

export async function authorizeCompanionMemoryCandidate(
  context: CompanionMemoryDecisionContext,
): Promise<CompanionMemoryAuthorization> {
  const explicit = localExplicitCandidate(context.input);
  if (explicit && sameExplicitEvidence(context.candidate, explicit)) {
    return {
      status: "authorized",
      source: "explicit",
      // Only local deterministic evidence is allowed to become persisted
      // evidence for an explicit request; the model's evidence is advisory.
      evidence: explicit.evidence,
    };
  }

  if (!context.confirmationVerifier) {
    return {
      status: "confirmation_required",
      errorCode: context.candidate.confirmationStatus === "confirmed"
        ? "confirmation-proof-missing"
        : "explicit-proof-missing",
    };
  }

  let proof: CompanionMemoryConfirmationProof | null = null;
  try {
    proof = await context.confirmationVerifier.verify(
      context.input,
      context.candidate,
      getCompanionMemoryCandidateId(context.candidate),
      context.signal,
    );
  } catch {
    proof = null;
  }
  if (!validConfirmationProof(proof, context.input, context.candidate)) {
    return {
      status: "confirmation_required",
      errorCode: "confirmation-proof-missing",
    };
  }

  return {
    status: "authorized",
    source: "confirmed",
    // Confirmation proves the candidate, but the model's evidence remains
    // untrusted. Persist only a bounded local proof label, never the model's
    // raw evidence or a copied confirmation transcript.
    evidence: "用户已在本地确认这条 Memory。",
  };
}

function isActiveAt(entry: MemoryEntry, now: number): boolean {
  return entry.status === "active"
    && (entry.expiresAt === null || Date.parse(entry.expiresAt) > now);
}

function safeCandidateText(value: string): string | null {
  const normalized = normalizeText(value);
  if (
    !normalized
    || Array.from(normalized).length > MEMORY_POLICY_MAX_TEXT_LENGTH
    || containsSensitiveCompanionText(normalized)
    || containsSensitiveMemoryText(normalized)
  ) return null;
  return normalized;
}

type PreferencePolarity = "positive" | "negative";

type PreferenceFact = {
  slot: string;
  polarity: PreferencePolarity;
};

type ProfileFact = {
  slot: "profile:name";
  value: string;
};

function normalizePreferenceObject(value: string): string {
  return normalizeCompanionMemoryComparisonText(value)
    .replace(/^(?:吃|喝)/u, "");
}

function parsePreferenceFact(value: string): PreferenceFact | null {
  const normalized = normalizeCompanionMemoryComparisonText(value)
    .replace(/^(?:用户|我)/u, "");
  const negative = normalized.match(/^(?:不喜欢|不爱|不吃|不喝)(.+)$/u);
  if (negative) {
    const slot = normalizePreferenceObject(negative[1]);
    return slot ? { slot, polarity: "negative" } : null;
  }
  const positive = normalized.match(/^(?:喜欢|爱吃|爱喝|爱)(.+)$/u);
  if (positive) {
    const slot = normalizePreferenceObject(positive[1]);
    return slot ? { slot, polarity: "positive" } : null;
  }
  return null;
}

function parseProfileFact(value: string): ProfileFact | null {
  const normalized = normalizeCompanionMemoryComparisonText(value)
    .replace(/^用户/u, "");
  const match = normalized.match(/^(?:我叫|我的昵称是)(.+)$/u);
  if (!match || !match[1]) return null;
  return { slot: "profile:name", value: match[1] };
}

function isSemanticallyEquivalent(left: MemoryEntry, right: MemoryCandidate): boolean {
  if (left.scope !== right.scope || left.type !== right.type) return false;
  if (
    normalizeCompanionMemoryComparisonText(left.content)
    === normalizeCompanionMemoryComparisonText(right.content)
  ) return true;

  if (left.type === "preference") {
    const leftFact = parsePreferenceFact(left.content);
    const rightFact = parsePreferenceFact(right.content);
    return Boolean(
      leftFact
      && rightFact
      && leftFact.slot === rightFact.slot
      && leftFact.polarity === rightFact.polarity,
    );
  }
  if (left.type === "fact") {
    const leftFact = parseProfileFact(left.content);
    const rightFact = parseProfileFact(right.content);
    return Boolean(leftFact && rightFact && leftFact.slot === rightFact.slot && leftFact.value === rightFact.value);
  }
  return false;
}

function isConflict(left: MemoryEntry, right: MemoryCandidate): boolean {
  if (left.scope !== right.scope || left.type !== right.type) return false;
  if (left.type === "preference") {
    const leftFact = parsePreferenceFact(left.content);
    const rightFact = parsePreferenceFact(right.content);
    return Boolean(
      leftFact
      && rightFact
      && leftFact.slot === rightFact.slot
      && leftFact.polarity !== rightFact.polarity,
    );
  }
  if (left.type === "fact") {
    const leftFact = parseProfileFact(left.content);
    const rightFact = parseProfileFact(right.content);
    return Boolean(
      leftFact
      && rightFact
      && leftFact.slot === rightFact.slot
      && leftFact.value !== rightFact.value,
    );
  }
  return false;
}

function decision(
  item: CompanionMemoryDecision,
): MemoryCandidateDecision {
  return {
    index: item.index,
    status: item.status,
    ...(item.scope ? { scope: item.scope } : {}),
    ...(item.type ? { type: item.type } : {}),
    ...(item.resourceId ? { resourceId: item.resourceId } : {}),
    ...(item.supersedesId ? { supersedesId: item.supersedesId } : {}),
    ...(item.errorCode ? { errorCode: item.errorCode } : {}),
  };
}

function persistenceInput(
  candidate: MemoryCandidate,
  authorization: Extract<CompanionMemoryAuthorization, { status: "authorized" }>,
  content: string,
  supersedesId: string | null,
): MemoryEntryInput {
  return {
    id: getCompanionMemoryRevisionId(candidate, supersedesId),
    scope: candidate.scope,
    type: candidate.type,
    content,
    source: authorization.source,
    evidence: authorization.evidence,
    sourceMessageId: candidate.sourceMessageId,
    confidence: candidate.confidence,
    expiresAt: candidate.expiresAt,
    status: "active",
    supersedesId,
    deletedAt: null,
  };
}

function findActiveMatches(
  repository: MemoryRepository,
  candidate: MemoryCandidate,
  now: number,
): MemoryEntry[] {
  return repository
    .list({ scope: candidate.scope })
    .filter((entry) => isActiveAt(entry, now) && entry.type === candidate.type);
}

function failureDecision(
  index: number,
  candidate: MemoryCandidate,
  errorCode: string,
): CompanionMemoryDecision {
  return {
    index,
    status: "failed",
    candidate,
    scope: candidate.scope,
    type: candidate.type,
    errorCode,
  };
}

export class CompanionMemoryPolicy implements CompanionMemoryService {
  constructor(private readonly options: CompanionMemoryPolicyOptions) {}

  async process(
    input: CompanionInput,
    candidates: readonly MemoryCandidate[],
    signal: AbortSignal,
  ): Promise<MemoryPolicyResult> {
    if (!candidates.length) {
      return { status: "not-requested", acceptedCount: 0, rejectedCount: 0, decisions: [] };
    }

    const decisions: MemoryCandidateDecision[] = [];
    let acceptedCount = 0;
    let rejectedCount = 0;
    let firstFailure: string | undefined;

    for (const [index, rawCandidate] of candidates.entries()) {
      if (signal.aborted) {
        decisions.push({ index, status: "cancelled", errorCode: "turn-invalidated" });
        rejectedCount += 1;
        continue;
      }

      const candidate = canonicalCandidate(input, rawCandidate);
      if (!candidate) {
        decisions.push({ index, status: "rejected", errorCode: "invalid-candidate" });
        rejectedCount += 1;
        continue;
      }
      const content = safeCandidateText(candidate.content);
      const evidence = safeCandidateText(candidate.evidence);
      if (!content || !evidence || containsSensitiveCompanionText(candidate.sourceMessageId)) {
        decisions.push({
          index,
          status: "rejected",
          scope: candidate.scope,
          type: candidate.type,
          errorCode: "sensitive-or-invalid-content",
        });
        rejectedCount += 1;
        continue;
      }

      const now = candidateNow(input);
      if (now === null) {
        decisions.push({
          index,
          status: "rejected",
          scope: candidate.scope,
          type: candidate.type,
          errorCode: "invalid-current-time",
        });
        rejectedCount += 1;
        continue;
      }
      if (candidate.lifetime === "temporal" && (
        candidate.expiresAt === null
        || Date.parse(candidate.expiresAt) <= now
      )) {
        decisions.push({
          index,
          status: "expired",
          scope: candidate.scope,
          type: candidate.type,
          errorCode: "candidate-expired",
        });
        rejectedCount += 1;
        continue;
      }

      const authorization = await authorizeCompanionMemoryCandidate({
        input,
        candidate,
        index,
        repository: this.options.repository,
        now,
        signal,
        confirmationVerifier: this.options.confirmationVerifier,
      });
      if (authorization.status === "confirmation_required") {
        decisions.push({
          index,
          status: "confirmation_required",
          scope: candidate.scope,
          type: candidate.type,
          errorCode: authorization.errorCode,
        });
        rejectedCount += 1;
        continue;
      }
      if (authorization.status === "rejected") {
        decisions.push({
          index,
          status: "rejected",
          scope: candidate.scope,
          type: candidate.type,
          errorCode: authorization.errorCode,
        });
        rejectedCount += 1;
        continue;
      }
      if (signal.aborted) {
        decisions.push({
          index,
          status: "cancelled",
          scope: candidate.scope,
          type: candidate.type,
          errorCode: "turn-invalidated",
        });
        rejectedCount += 1;
        continue;
      }

      let activeEntries: MemoryEntry[];
      try {
        activeEntries = findActiveMatches(this.options.repository, candidate, now);
      } catch {
        const failed = failureDecision(index, candidate, "memory-read-failed");
        decisions.push(decision(failed));
        rejectedCount += 1;
        firstFailure ??= failed.errorCode;
        continue;
      }

      const normalizedContent = normalizeCompanionMemoryComparisonText(content);
      const duplicate = activeEntries.find((entry) =>
        normalizeCompanionMemoryComparisonText(entry.content) === normalizedContent
          || isSemanticallyEquivalent(entry, candidate),
      );
      if (duplicate) {
        const duplicateDecision: CompanionMemoryDecision = {
          index,
          status: "duplicate",
          candidate,
          scope: candidate.scope,
          type: candidate.type,
          resourceId: duplicate.id,
        };
        decisions.push(decision(duplicateDecision));
        continue;
      }

      const conflict = activeEntries.find((entry) => isConflict(entry, candidate));
      const inputValue = persistenceInput(candidate, authorization, content, conflict?.id ?? null);
      try {
        // The check immediately before the repository call is the write gate.
        // A late abort after a repository-confirmed write never rewrites the
        // domain result; the Harness separately suppresses the UI commit.
        if (signal.aborted) {
          decisions.push({
            index,
            status: "cancelled",
            scope: candidate.scope,
            type: candidate.type,
            errorCode: "turn-invalidated",
          });
          rejectedCount += 1;
          continue;
        }
        if (conflict) {
          const replaced = this.options.repository.supersede(conflict.id, inputValue);
          if (!replaced) {
            const failed = failureDecision(index, candidate, "memory-supersede-failed");
            decisions.push(decision(failed));
            rejectedCount += 1;
            firstFailure ??= failed.errorCode;
            continue;
          }
          const replacedDecision: CompanionMemoryDecision = {
            index,
            status: "superseded",
            candidate,
            scope: candidate.scope,
            type: candidate.type,
            resourceId: replaced.id,
            supersedesId: conflict.id,
          };
          decisions.push(decision(replacedDecision));
          acceptedCount += 1;
          continue;
        }
        const saved = this.options.repository.save(inputValue);
        if (!saved) {
          const failed = failureDecision(index, candidate, "memory-save-failed");
          decisions.push(decision(failed));
          rejectedCount += 1;
          firstFailure ??= failed.errorCode;
          continue;
        }
        const inserted: CompanionMemoryDecision = {
          index,
          status: "inserted",
          candidate,
          scope: candidate.scope,
          type: candidate.type,
          resourceId: saved.id,
        };
        decisions.push(decision(inserted));
        acceptedCount += 1;
      } catch {
        const failed = failureDecision(index, candidate, conflict ? "memory-supersede-threw" : "memory-save-threw");
        decisions.push(decision(failed));
        rejectedCount += 1;
        firstFailure ??= failed.errorCode;
      }
    }

    const hasFailure = decisions.some((item) => item.status === "failed");
    const hasCancellation = decisions.some((item) => item.status === "cancelled");
    return {
      status: hasFailure
        ? "failed"
        : hasCancellation
          ? "cancelled"
          : acceptedCount > 0
            ? "succeeded"
            : "ignored",
      acceptedCount,
      rejectedCount,
      decisions,
      ...(firstFailure ? { errorCode: firstFailure } : {}),
    };
  }
}

export function createCompanionMemoryService(
  repository: MemoryRepository = createCompanionMemoryRepository(),
  options: Omit<CompanionMemoryPolicyOptions, "repository"> = {},
): CompanionMemoryService {
  return new CompanionMemoryPolicy({ repository, ...options });
}
