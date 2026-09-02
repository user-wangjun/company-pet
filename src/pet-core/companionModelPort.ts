import type { CompanionChatContext } from "./companionContext";
import {
  CompanionContextPrivacyError,
  CompanionContextTrustError,
  filterCompanionContextForRemote,
  isTrustedCompanionChatContext,
} from "./companionContext";
import { CompanionContextBudgetError } from "./companionContextBudget";
import {
  CompanionModelCodecError,
  companionModelCodec,
  encodeLocalCompanionModelRequest,
  selectCompanionModelCodecOutput,
  type CompanionModelCodec,
} from "./companionModelCodec";
import type { CompanionChatProviderInfo } from "./companionChatRuntime";
import type {
  CompanionInput,
  CompanionModelResponse,
} from "./companionHarnessTypes";
import {
  CompanionChatProviderError,
  type CompanionChatProviderErrorKind,
} from "./companionChatProvider";
import {
  DEFAULT_BUNDLED_OLLAMA_TIMEOUT_MS,
  ProviderAdapterError,
  type ProviderCapabilities,
  type ProviderAdapter,
  type ProviderGenerateResponse,
} from "./companionProviderAdapter";
import type { ProviderResolver } from "./companionProviderResolver";

export type CompanionModelPortInfo = CompanionChatProviderInfo;

export interface HarnessModelRequest {
  input: CompanionInput;
  context: CompanionChatContext;
  signal?: AbortSignal;
}

/**
 * The immutable provider view for one Harness Turn. The adapter, metadata and
 * capabilities are captured from the same resolver result, and generate()
 * closes over that adapter instead of resolving the Provider again.
 */
export interface ResolvedCompanionModelTurn {
  readonly adapter: ProviderAdapter;
  readonly info: CompanionModelPortInfo;
  readonly capabilities: ProviderCapabilities;
  readonly providerProfileId?: string;
  readonly protocol?: string;
  generate(request: HarnessModelRequest): Promise<CompanionModelResponse>;
}

/**
 * Harness-owned domain port. Provider protocol details stay behind the
 * implementation and are intentionally absent from this contract.
 */
export interface CompanionModelPort {
  /**
   * Resolve exactly one Provider snapshot for the beginning of a Turn.
   * Implementations must not expose a dynamic resolver-backed getter.
   */
  beginTurn(): ResolvedCompanionModelTurn;
  /**
   * Kept as a compatibility entry point for direct callers. Harness code uses
   * beginTurn() and then calls the returned snapshot for the full Turn.
   */
  readonly info: CompanionModelPortInfo;
  generate(request: HarnessModelRequest): Promise<CompanionModelResponse>;
}

export type CompanionModelPortOptions = {
  resolver: ProviderResolver;
  codec?: CompanionModelCodec;
  info?: CompanionModelPortInfo;
  timeoutMs?: number;
  temperature?: number;
  maxOutputTokens?: number;
  /**
   * Harness-owned local generation hook. It receives the immutable input and
   * context snapshot so a local reply cannot drift to a newly active pet.
   */
  localGenerate?: (request: HarnessModelRequest) => string | Promise<string>;
};

function errorKind(value: unknown): CompanionChatProviderErrorKind {
  if (value instanceof CompanionChatProviderError) return value.kind;
  if (value instanceof ProviderAdapterError) return value.kind;
  if (value instanceof CompanionModelCodecError) return "malformed-response";
  if (value instanceof CompanionContextPrivacyError) return "content-safety";
  if (
    value instanceof CompanionContextTrustError
    || value instanceof CompanionContextBudgetError
  ) return "configuration";
  return "network";
}

function errorMessage(value: unknown, kind: CompanionChatProviderErrorKind): string {
  if (value instanceof CompanionChatProviderError) return value.userMessage;
  if (value instanceof ProviderAdapterError) return value.userMessage;
  if (value instanceof CompanionModelCodecError) return value.message;
  if (kind === "content-safety") return "这类内容未通过远程隐私门禁。";
  if (kind === "configuration") return "远程模型请求配置无效，未发送请求。";
  if (kind === "cancelled") return "这次回复已停止。";
  return "聊天服务暂时没接上，稍后再试。";
}

function normalizePortError(error: unknown): CompanionChatProviderError {
  if (error instanceof CompanionChatProviderError) return error;
  const kind = errorKind(error);
  const status = error instanceof ProviderAdapterError
    ? error.status
    : undefined;
  return new CompanionChatProviderError(errorMessage(error, kind), kind, status);
}

const UNRESOLVED_COMPANION_MODEL_PORT_INFO: CompanionModelPortInfo = Object.freeze({
  kind: "local",
  provider: "未解析 Provider",
  target: "未解析",
  disclosure: "当前 Provider 尚未解析。",
});

function snapshotInfo(adapter: ProviderAdapter): CompanionModelPortInfo {
  return Object.freeze({ ...adapter.info });
}

function snapshotCapabilities(adapter: ProviderAdapter): ProviderCapabilities {
  return Object.freeze({ ...adapter.capabilities });
}

function createResolvedCompanionModelTurn(
  adapter: ProviderAdapter,
  codec: CompanionModelCodec,
  timeoutMs: number,
  temperature: number | undefined,
  maxOutputTokens: number | undefined,
  localGenerate: CompanionModelPortOptions["localGenerate"],
): ResolvedCompanionModelTurn {
  const info = snapshotInfo(adapter);
  const capabilities = snapshotCapabilities(adapter);
  const selected = selectCompanionModelCodecOutput(capabilities);

  const generate = async (
    request: HarnessModelRequest,
  ): Promise<CompanionModelResponse> => {
    if (request.signal?.aborted || request.input.signal?.aborted) {
      throw new CompanionChatProviderError("这次回复已停止。", "cancelled");
    }
    if (info.kind === "remote" && !isTrustedCompanionChatContext(request.context)) {
      throw new CompanionChatProviderError(
        "远程生成需要由正式 ContextBuilder 构建安全上下文。",
        "configuration",
      );
    }
    if (
      info.kind === "remote"
      && (
        request.context.userInput !== request.input.message
        || request.context.petId !== request.input.petId
        || (
          request.input.contextEpoch !== undefined
          && request.context.contextEpoch !== request.input.contextEpoch
        )
      )
    ) {
      throw new CompanionChatProviderError(
        "当前输入与受信 Context 不一致，未发送请求。",
        "configuration",
      );
    }

    try {
      if (info.kind === "remote" && !isTrustedCompanionChatContext(request.context)) {
        throw new CompanionContextTrustError();
      }
      if (
        info.kind === "remote"
        && (
          request.context.userInput !== request.input.message
          || request.context.petId !== request.input.petId
          || (
            request.input.contextEpoch !== undefined
            && request.context.contextEpoch !== request.input.contextEpoch
          )
        )
      ) {
        throw new CompanionContextTrustError();
      }
      let providerResponse: ProviderGenerateResponse;
      // The deterministic `local` profile is the only path that uses the
      // harness-provided fixed reply. `ollama-local` is also private, but it
      // must still call its real local model adapter.
      if (info.kind === "local" && adapter.protocol === "local" && localGenerate) {
        providerResponse = {
          text: await localGenerate(request),
          metadata: {
            providerId: adapter.id,
            model: adapter.info.target,
          },
        };
      } else {
        const providerRequest = info.kind === "remote" || isTrustedCompanionChatContext(request.context)
          ? codec.encode(
              info.kind === "remote"
                ? filterCompanionContextForRemote(request.context)
                : request.context,
              capabilities,
              {
                timeoutMs,
                ...(temperature === undefined ? {} : { temperature }),
                ...(maxOutputTokens === undefined ? {} : { maxOutputTokens }),
              },
            )
          : encodeLocalCompanionModelRequest(request.input.message, {
              timeoutMs,
              ...(temperature === undefined ? {} : { temperature }),
              ...(maxOutputTokens === undefined ? {} : { maxOutputTokens }),
            });
        providerResponse = await adapter.generate({
          ...providerRequest,
          signal: request.signal,
        });
      }
      return codec.decode(providerResponse, {
        mode: selected.mode,
        sourceMessageId: request.input.sourceMessageId,
        petId: request.input.petId,
      });
    } catch (error) {
      throw normalizePortError(error);
    }
  };

  return Object.freeze({
    adapter,
    info,
    capabilities,
    providerProfileId: adapter.id,
    protocol: adapter.protocol,
    generate,
  });
}

/**
 * Creates the single Harness-owned model port. Provider resolution is deferred
 * until beginTurn(); a normal Turn then resolves one adapter, encodes once,
 * calls that adapter once, and decodes locally. No retry, planner, tool loop,
 * or second model call exists in this path.
 */
export function createCompanionModelPort(
  options: CompanionModelPortOptions,
): CompanionModelPort {
  const codec = options.codec ?? companionModelCodec;
  const timeoutMs = Math.max(1, options.timeoutMs ?? 15_000);
  const info = Object.freeze({
    ...(options.info ?? UNRESOLVED_COMPANION_MODEL_PORT_INFO),
  });

  const beginTurn = (): ResolvedCompanionModelTurn => {
    try {
      const adapter = options.resolver.resolve();
      const effectiveTimeoutMs = adapter.protocol === "ollama-local"
        ? Math.max(timeoutMs, DEFAULT_BUNDLED_OLLAMA_TIMEOUT_MS)
        : timeoutMs;
      return createResolvedCompanionModelTurn(
        adapter,
        codec,
        effectiveTimeoutMs,
        options.temperature,
        options.maxOutputTokens,
        options.localGenerate,
      );
    } catch (error) {
      throw normalizePortError(error);
    }
  };

  return {
    info,
    beginTurn,
    async generate(request) {
      return beginTurn().generate(request);
    },
  };
}
