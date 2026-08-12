export type CompanionContextEpoch = number;

let nextEpoch = 0;

/**
 * An epoch is an internal model-context boundary. It is intentionally kept
 * out of the visible chat record and is not persisted as a conversation.
 */
export function createCompanionContextEpoch(): CompanionContextEpoch {
  nextEpoch += 1;
  return nextEpoch;
}

const EXPLICIT_TOPIC_CHANGE_PATTERNS = [
  /换(?:个|一个|下一个)话题/u,
  /我们聊点别的/u,
  /说点别的/u,
  /先不(?:说|聊)这个/u,
  /不(?:说|聊)这个了/u,
  /这个先放一边/u,
];

/**
 * Only explicit topic-change language starts a new model context. Ordinary
 * follow-ups must keep using the current epoch, even when the visible record
 * is long.
 */
export function isExplicitCompanionTopicChange(text: string): boolean {
  const normalized = text.replace(/\s+/gu, "").trim();
  return normalized.length > 0
    && EXPLICIT_TOPIC_CHANGE_PATTERNS.some((pattern) => pattern.test(normalized));
}
