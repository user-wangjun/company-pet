import type {
  RepeatRule,
  RepeatType,
  SchedulePrecision,
  Task,
  TaskDatabase,
  TaskDraft,
} from "../task-core/types";
import { containsSensitiveCompanionText } from "./companionPrivacy";

export type TaskCandidateExplicitness =
  | "explicit"
  | "vague"
  | "hypothetical"
  | "joking"
  | "negated"
  | "time_ambiguous";

export type TaskCandidateRiskLevel = "low" | "medium" | "high";
export type TaskExtractionClassification = TaskCandidateExplicitness | "not_task";
export type TaskCandidateRepeatType = Exclude<RepeatType, "none">;

export type TaskCandidate = {
  title: string;
  dueAt: string | null;
  schedulePrecision: SchedulePrecision;
  remindAt: string | null;
  /** Omitted unless the user explicitly used a repeat expression. */
  repeatType?: TaskCandidateRepeatType;
  repeatRule?: RepeatRule;
  timezone?: string;
  /** Legacy convention: JavaScript Date#getTimezoneOffset (UTC minus local). */
  timezoneOffsetMinutes: number;
  sourceMessageId: string;
  evidence: string;
  confidence: number;
  riskLevel: TaskCandidateRiskLevel;
  explicitness: TaskCandidateExplicitness;
  needsConfirmation: boolean;
  confirmationReason: string | null;
  reminderRequested: boolean;
};

export type TaskExtractorOptions = {
  now?: Date | string;
  timezone?: string;
  /** Legacy convention: UTC minus local; do not pass CompanionInput.utcOffsetMinutes directly. */
  timezoneOffsetMinutes?: number;
};

export type TaskOperationType = "complete" | "cancel" | "postpone" | "reschedule";

export type TaskOperationCandidate = {
  operation: TaskOperationType;
  targetTitle: string;
  dueAt: string | null;
  schedulePrecision: SchedulePrecision;
  remindAt: string | null;
  timezone?: string;
  /** Legacy convention: JavaScript Date#getTimezoneOffset (UTC minus local). */
  timezoneOffsetMinutes: number;
  sourceMessageId: string;
  evidence: string;
  explicitness: TaskCandidateExplicitness;
  confidence: number;
  needsConfirmation: boolean;
  confirmationReason: string | null;
};

export type TaskCandidateConfirmation = "confirm" | "cancel" | "other";

export type PendingTaskCandidate = {
  petId: string;
  candidate: TaskCandidate;
};

export type TaskReferenceMatch = {
  status: "found" | "not_found" | "ambiguous";
  task: Task | null;
};

type LocalParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
};

type ParsedTime = {
  hour: number;
  minute: number;
  text: string;
  exact: boolean;
  ambiguous: boolean;
};

type ParsedTiming = {
  dateKey: string | null;
  time: ParsedTime | null;
  dateKnown: boolean;
  timeKnown: boolean;
  timeAmbiguous: boolean;
  matchedText: string[];
  repeatType?: TaskCandidateRepeatType;
  repeatRule?: RepeatRule;
};

const DATE_ONLY_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const CHINESE_DIGITS: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10,
};
const WEEKDAY_VALUES: Record<string, number> = {
  日: 0,
  天: 0,
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 0,
};
const TIME_PERIODS = /凌晨|早上|上午|中午|下午|傍晚|晚上/u;
const VAGUE_EXPRESSION = /最近|有空|抽空|改天|找时间|哪天|有时间|以后|将来|想(?:要)?|希望|考虑|应该|该.+了/u;
const NEGATED_EXPRESSION = /(?:别|不要|不用|无需|不必|不需要|别再|不要给我|不用帮我)\s*(?:提醒|记|记录|创建|安排|加入待办|设为待办)/u;
const HYPOTHETICAL_EXPRESSION = /如果|假如|假设|要是|万一|也许|可能|或许|设想|假定/u;
const JOKING_EXPRESSION = /开玩笑|玩笑|说着玩|逗你|随口说|哈哈.*(?:提醒|记|任务)|(?:提醒|记)一下.*哈哈/u;
const TASK_COMMAND = /提醒我|叫我|通知我|记一下|记下|安排(?:一个)?(?:待办|任务)?|加入待办|创建(?:一个)?任务/u;
const TASK_TIME_SIGNAL = /今天|明天|后天|大后天|下周|本周|这周|每周|每天|每日|星期|礼拜|\d{1,4}年?\d{1,2}月|\d{4}-\d{1,2}-\d{1,2}|\d{1,2}:\d{2}|点|时/u;
const TASK_CONTENT_SIGNAL = /交|做|完成|买|整理|复盘|开会|提交|写|准备|预约|处理|学习|学|看|打扫|发布|检查|联系|参加|缴费|报名|练习|喝|吃|寄|取|申请|安排|开始|结束|阅读|跑步|运动|健身|清理|备份|更新|修理|回复|发给|送/u;
const NICKNAME_EXPRESSION = /^(?:以后|之后)\s*叫我\s*[^，。！？!\s]{1,12}[。！？!?]?$/u;
const SENSITIVE_TASK_TEXT = /医疗|诊断|病史|吃药|用药|处方|治疗|法律|诉讼|报警|转账|银行卡|信用卡|密码|账号|投资|借贷|自杀|自伤|伤害/u;
const MEDIUM_RISK_TASK_TEXT = /考试|合同|客户|发布|上线|截止|紧急|重要|工作/u;
const COMMANDS_TO_REMOVE = /(?:请你?|麻烦你?|帮我|务必|提醒我|提醒一下|叫我|通知我|记一下|记下|记住|加入待办|创建(?:一个)?任务|安排(?:一个)?(?:待办|任务)?)/gu;

function isSensitiveTaskInput(input: string): boolean {
  return containsSensitiveCompanionText(input) || SENSITIVE_TASK_TEXT.test(input);
}

function normalizeText(value: string): string {
  return value.replace(/\r\n?/g, "\n").replace(/\s+/g, " ").trim();
}

function stripSentencePunctuation(value: string): string {
  return value.replace(/^[\s，,：:、。！？!?]+|[\s，,：:、。！？!?]+$/gu, "").trim();
}

function getTimezoneOffsetMinutes(options: TaskExtractorOptions): number {
  return Number.isFinite(options.timezoneOffsetMinutes)
    ? Number(options.timezoneOffsetMinutes)
    : new Date().getTimezoneOffset();
}

function getTimezoneName(options: TaskExtractorOptions): string {
  if (options.timezone?.trim()) return options.timezone.trim();
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
  } catch {
    return "local";
  }
}

function getNowMs(value: Date | string | undefined): number {
  if (value instanceof Date) return Number.isFinite(value.getTime()) ? value.getTime() : Date.now();
  if (typeof value === "string") {
    const parsed = Date.parse(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return Date.now();
}

function getLocalParts(nowMs: number, timezoneOffsetMinutes: number): LocalParts {
  const shifted = new Date(nowMs - timezoneOffsetMinutes * 60_000);
  return {
    year: shifted.getUTCFullYear(),
    month: shifted.getUTCMonth() + 1,
    day: shifted.getUTCDate(),
    hour: shifted.getUTCHours(),
    minute: shifted.getUTCMinutes(),
  };
}

function dateKeyFromParts(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function dateKeyToParts(value: string): { year: number; month: number; day: number } | null {
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/u);
  if (!match) return null;
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

function addDays(dateKey: string, days: number): string {
  const parts = dateKeyToParts(dateKey);
  if (!parts) return dateKey;
  const date = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + days));
  return dateKeyFromParts(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
}

function localDateTimeToIso(
  dateKey: string,
  hour: number,
  minute: number,
  timezoneOffsetMinutes: number,
): string {
  const parts = dateKeyToParts(dateKey);
  if (!parts) return dateKey;
  return new Date(
    Date.UTC(parts.year, parts.month - 1, parts.day, hour, minute) + timezoneOffsetMinutes * 60_000,
  ).toISOString();
}

function parseNumber(value: string): number | null {
  const normalized = value.trim();
  if (/^\d+$/u.test(normalized)) return Number(normalized);
  if (!normalized || !Array.from(normalized).every((char) => char in CHINESE_DIGITS)) return null;
  if (normalized.length === 1) return CHINESE_DIGITS[normalized] ?? null;
  if (normalized.includes("十")) {
    const [tens, ones] = normalized.split("十");
    return (tens ? CHINESE_DIGITS[tens] ?? 0 : 1) * 10 + (ones ? CHINESE_DIGITS[ones] ?? 0 : 0);
  }
  return Number(Array.from(normalized).map((char) => CHINESE_DIGITS[char]).join(""));
}

function parseDateToken(token: string, base: LocalParts): string | null {
  const normalized = token.replace(/\s+/g, "");
  if (normalized === "今天") return dateKeyFromParts(base.year, base.month, base.day);
  if (normalized === "明天") return addDays(dateKeyFromParts(base.year, base.month, base.day), 1);
  if (normalized === "后天") return addDays(dateKeyFromParts(base.year, base.month, base.day), 2);
  if (normalized === "大后天") return addDays(dateKeyFromParts(base.year, base.month, base.day), 3);

  const explicit = normalized.match(/^(?:(\d{4})年)?(\d{1,2}|[一二三四五六七八九十]{1,3})月(\d{1,2}|[一二三四五六七八九十]{1,3})[日号]$/u);
  if (explicit) {
    const month = parseNumber(explicit[2]);
    const day = parseNumber(explicit[3]);
    const year = explicit[1] ? Number(explicit[1]) : base.year;
    if (!month || !day) return null;
    const candidate = new Date(Date.UTC(year, month - 1, day));
    if (candidate.getUTCMonth() + 1 !== month || candidate.getUTCDate() !== day) return null;
    const key = dateKeyFromParts(year, month, day);
    return !explicit[1] && key < dateKeyFromParts(base.year, base.month, base.day)
      ? dateKeyFromParts(year + 1, month, day)
      : key;
  }

  const iso = normalized.match(/^(\d{4})[-年](\d{1,2})[-月](\d{1,2})日?$/u);
  if (iso) {
    const year = Number(iso[1]);
    const month = Number(iso[2]);
    const day = Number(iso[3]);
    const candidate = new Date(Date.UTC(year, month - 1, day));
    return candidate.getUTCMonth() + 1 === month && candidate.getUTCDate() === day
      ? dateKeyFromParts(year, month, day)
      : null;
  }

  const weekday = normalized.match(/^(?:(下|本|这)?(?:周|星期|礼拜))([一二三四五六日天七])$/u);
  if (weekday) {
    const target = WEEKDAY_VALUES[weekday[2]];
    const currentDate = new Date(Date.UTC(base.year, base.month - 1, base.day));
    const currentWeekday = currentDate.getUTCDay();
    if (weekday[1] === "下") {
      const daysFromMonday = (currentWeekday + 6) % 7;
      return addDays(dateKeyFromParts(base.year, base.month, base.day), 7 - daysFromMonday + ((target + 6) % 7));
    }
    if (weekday[1] === "本" || weekday[1] === "这") {
      const daysFromMonday = (currentWeekday + 6) % 7;
      return addDays(dateKeyFromParts(base.year, base.month, base.day), -daysFromMonday + ((target + 6) % 7));
    }
    const delta = (target - currentWeekday + 7) % 7;
    return addDays(dateKeyFromParts(base.year, base.month, base.day), delta);
  }

  return null;
}

function parseRepeat(input: string): {
  repeatType?: TaskCandidateRepeatType;
  repeatRule?: RepeatRule;
  token?: string;
} {
  if (/每天|每日/u.test(input)) return { repeatType: "daily", token: input.match(/每天|每日/u)?.[0] };
  const weekday = input.match(/每(?:周|星期|礼拜)([一二三四五六日天七])/u);
  if (weekday) {
    return {
      repeatType: "custom",
      repeatRule: { weekdays: [WEEKDAY_VALUES[weekday[1]]] },
      token: weekday[0],
    };
  }
  if (/每周|每星期|每礼拜/u.test(input)) {
    return { repeatType: "weekly", token: input.match(/每周|每星期|每礼拜/u)?.[0] };
  }
  return {};
}

function parseTime(input: string): ParsedTime | null {
  const colon = input.match(/(凌晨|早上|上午|中午|下午|傍晚|晚上)?\s*(\d{1,2}):(\d{2})/u);
  if (colon) {
    let hour = Number(colon[2]);
    const minute = Number(colon[3]);
    if (hour > 23 || minute > 59) return null;
    const period = colon[1] ?? "";
    if (period && hour < 12 && ["下午", "傍晚", "晚上"].includes(period)) hour += 12;
    if (period === "凌晨" && hour === 12) hour = 0;
    if ((period === "上午" || period === "早上") && hour === 12) hour = 0;
    return { hour, minute, text: colon[0], exact: true, ambiguous: !period && hour <= 12 };
  }

  const point = input.match(/(凌晨|早上|上午|中午|下午|傍晚|晚上)?\s*([0-9]{1,2}|[零〇一二两三四五六七八九十]{1,3})\s*(?:点|时)(半|一刻|三刻|([0-5]?\d)分?)?/u);
  if (!point) return null;
  let hour = parseNumber(point[2]);
  if (hour === null) return null;
  let minute = 0;
  if (point[3] === "半") minute = 30;
  if (point[3] === "一刻") minute = 15;
  if (point[3] === "三刻") minute = 45;
  if (point[4]) minute = Number(point[4]);
  if (hour > 23 || minute > 59) return null;
  const period = point[1] ?? "";
  if (period && hour < 12 && ["下午", "傍晚", "晚上", "中午"].includes(period)) hour += 12;
  if (period === "凌晨" && hour === 12) hour = 0;
  if ((period === "上午" || period === "早上") && hour === 12) hour = 0;
  const hasExplicitPeriod = Boolean(period);
  return {
    hour,
    minute,
    text: point[0],
    exact: true,
    ambiguous: !hasExplicitPeriod && hour <= 12,
  };
}

function parseTaskTiming(
  input: string,
  options: TaskExtractorOptions,
): ParsedTiming {
  const timezoneOffsetMinutes = getTimezoneOffsetMinutes(options);
  const base = getLocalParts(getNowMs(options.now), timezoneOffsetMinutes);
  const repeat = parseRepeat(input);
  const relative = input.match(/大后天|后天|明天|今天/u)?.[0];
  const explicitDate = input.match(/(?:(?:\d{4}年)?\d{1,2}月\d{1,2}[日号]|\d{4}[-年]\d{1,2}[-月]\d{1,2}日?)/u)?.[0];
  const weekday = input.match(/(?<![一二三四五六七八九十])(?:(?:下|本|这)?(?:周|星期|礼拜)[一二三四五六日天七])/u)?.[0];
  const repeatWeekday = input.match(/每(?:周|星期|礼拜)[一二三四五六日天七]/u)?.[0];
  const dateToken = relative ?? explicitDate ?? weekday ?? (repeatWeekday ? repeatWeekday.slice(1) : undefined);
  const dateKey = dateToken ? parseDateToken(dateToken, base) : null;
  const time = parseTime(input);
  const periodOnly = !time ? input.match(TIME_PERIODS)?.[0] ?? null : null;
  const timeAmbiguous = Boolean(periodOnly || (time && time.ambiguous) || (time && !dateKey));
  return {
    dateKey,
    time,
    dateKnown: Boolean(dateKey),
    timeKnown: Boolean(time),
    timeAmbiguous,
    matchedText: [repeatWeekday ? undefined : dateToken, repeat.token, time?.text, periodOnly].filter(
      (value): value is string => Boolean(value),
    ),
    repeatType: repeat.repeatType,
    repeatRule: repeat.repeatRule,
  };
}

function hasMemoryOnlyShape(input: string): boolean {
  return /^(?:(?:请|请你|帮我)\s*)?(?:务必\s*)?(?:记住|记下)\s*(?:我|我的|以后|之后)/u.test(input)
    && !TASK_TIME_SIGNAL.test(input)
    && !/提醒|待办|任务/u.test(input);
}

function hasTaskSignal(input: string): boolean {
  return TASK_COMMAND.test(input)
    || (TASK_TIME_SIGNAL.test(input) && TASK_CONTENT_SIGNAL.test(input));
}

function removeMatchedText(value: string, matchedText: readonly string[]): string {
  return matchedText.reduce((current, token) => current.replace(token, " "), value);
}

function extractTaskTitle(input: string, timing: ParsedTiming): string {
  let title = removeMatchedText(input, timing.matchedText);
  title = title.replace(COMMANDS_TO_REMOVE, " ");
  title = title
    .replace(/^(?:在|于|到|把|要|去|给我|帮我|请)\s*/u, "")
    .replace(/\s*(?:一下|吧|哦|呀|喽)$/u, "")
    .replace(/^[，,：:、\s]+|[，,：:、\s]+$/gu, "")
    .trim();
  return stripSentencePunctuation(title);
}

function classifyWithTiming(input: string, timing: ParsedTiming, title: string): TaskExtractionClassification {
  if (NICKNAME_EXPRESSION.test(input)) return "not_task";
  if (NEGATED_EXPRESSION.test(input)) return "negated";
  if (HYPOTHETICAL_EXPRESSION.test(input)) return "hypothetical";
  if (JOKING_EXPRESSION.test(input)) return "joking";
  if (VAGUE_EXPRESSION.test(input) && !TASK_COMMAND.test(input)) return "vague";
  if (hasMemoryOnlyShape(input) || !hasTaskSignal(input) || !title) return "not_task";
  if (!timing.dateKnown || timing.timeAmbiguous || (/提醒|叫我|通知我/u.test(input) && !timing.timeKnown)) {
    return "time_ambiguous";
  }
  return "explicit";
}

function getRiskLevel(input: string): TaskCandidateRiskLevel {
  if (SENSITIVE_TASK_TEXT.test(input)) return "high";
  if (MEDIUM_RISK_TASK_TEXT.test(input)) return "medium";
  return "low";
}

function buildConfirmationReason(
  explicitness: TaskCandidateExplicitness,
  riskLevel: TaskCandidateRiskLevel,
  timing: ParsedTiming,
  reminderRequested: boolean,
): string | null {
  if (explicitness === "time_ambiguous") {
    if (!timing.dateKnown) return "还没有明确日期，不能把没有日期的事项默认为今天。";
    if (reminderRequested && !timing.timeKnown) return "提醒时间还不明确，需要你确认具体时间。";
    return "时间表达不够明确，需要你确认后再写入任务。";
  }
  if (riskLevel === "high") return "这件事涉及敏感或高影响内容，需要你明确确认。";
  if (riskLevel === "medium") return "这件事影响较高，需要你明确确认。";
  return null;
}

function buildDueAt(
  timing: ParsedTiming,
  timezoneOffsetMinutes: number,
): { dueAt: string | null; schedulePrecision: SchedulePrecision } {
  if (!timing.dateKey) return { dueAt: null, schedulePrecision: "date" };
  if (timing.time && !timing.time.ambiguous) {
    return {
      dueAt: localDateTimeToIso(timing.dateKey, timing.time.hour, timing.time.minute, timezoneOffsetMinutes),
      schedulePrecision: "datetime",
    };
  }
  return { dueAt: timing.dateKey, schedulePrecision: "date" };
}

export function classifyTaskExpression(
  text: string,
  options: TaskExtractorOptions = {},
): TaskExtractionClassification {
  const input = normalizeText(text);
  if (!input) return "not_task";
  if (isSensitiveTaskInput(input)) return "not_task";
  const timing = parseTaskTiming(input, options);
  const title = extractTaskTitle(input, timing);
  return classifyWithTiming(input, timing, title);
}

export function parseTaskTimingForTest(
  text: string,
  options: TaskExtractorOptions = {},
): {
  dueAt: string | null;
  schedulePrecision: SchedulePrecision;
  timezoneOffsetMinutes: number;
  repeatType?: TaskCandidateRepeatType;
  repeatRule?: RepeatRule;
  timeAmbiguous: boolean;
} {
  const input = normalizeText(text);
  const timing = parseTaskTiming(input, options);
  const timezoneOffsetMinutes = getTimezoneOffsetMinutes(options);
  return {
    ...buildDueAt(timing, timezoneOffsetMinutes),
    timezoneOffsetMinutes,
    repeatType: timing.repeatType,
    repeatRule: timing.repeatRule,
    timeAmbiguous: timing.timeAmbiguous,
  };
}

export function extractTaskCandidate(
  text: string,
  sourceMessageId: string,
  options: TaskExtractorOptions = {},
): TaskCandidate | null {
  const evidence = text.trim();
  const input = normalizeText(text);
  const normalizedSourceMessageId = sourceMessageId.trim();
  if (
    !input ||
    !evidence ||
    !normalizedSourceMessageId ||
    isSensitiveTaskInput(input) ||
    containsSensitiveCompanionText(evidence) ||
    containsSensitiveCompanionText(normalizedSourceMessageId)
  ) return null;

  const timezoneOffsetMinutes = getTimezoneOffsetMinutes(options);
  const timing = parseTaskTiming(input, options);
  const title = extractTaskTitle(input, timing);
  const explicitness = classifyWithTiming(input, timing, title);
  if (explicitness !== "explicit" && explicitness !== "time_ambiguous") return null;

  const riskLevel = getRiskLevel(input);
  const reminderRequested = /提醒|叫我|通知我/u.test(input);
  const schedule = buildDueAt(timing, timezoneOffsetMinutes);
  const confirmationReason = buildConfirmationReason(
    explicitness,
    riskLevel,
    timing,
    reminderRequested,
  );
  const needsConfirmation = Boolean(
    explicitness !== "explicit"
      || riskLevel !== "low"
      || !schedule.dueAt
      || (reminderRequested && !timing.timeKnown),
  );
  const candidate: TaskCandidate = {
    title,
    ...schedule,
    remindAt: reminderRequested && timing.time && !timing.time.ambiguous && schedule.dueAt
      ? schedule.dueAt
      : null,
    timezone: getTimezoneName(options),
    timezoneOffsetMinutes,
    sourceMessageId: normalizedSourceMessageId,
    evidence,
    confidence: needsConfirmation ? (riskLevel === "high" ? 0.62 : 0.68) : 0.96,
    riskLevel,
    explicitness,
    needsConfirmation,
    confirmationReason,
    reminderRequested,
  };
  if (timing.repeatType) candidate.repeatType = timing.repeatType;
  if (timing.repeatRule) candidate.repeatRule = timing.repeatRule;
  return candidate;
}

export function canAutoCreateTask(candidate: TaskCandidate): boolean {
  return candidate.explicitness === "explicit"
    && !candidate.needsConfirmation
    && candidate.riskLevel === "low"
    && Boolean(candidate.dueAt)
    && (!candidate.reminderRequested || Boolean(candidate.remindAt));
}

export function taskDraftFromCandidate(
  candidate: TaskCandidate,
  createdByPetId: string,
): TaskDraft {
  return {
    title: candidate.title,
    dueAt: candidate.dueAt,
    schedulePrecision: candidate.schedulePrecision,
    remindAt: candidate.remindAt,
    repeatType: candidate.repeatType ?? "none",
    repeatRule: candidate.repeatRule ?? null,
    sourceMessageId: candidate.sourceMessageId,
    evidence: candidate.evidence,
    createdByPetId: createdByPetId.trim() || null,
  };
}

export function resolveTaskCandidateConfirmation(text: string): TaskCandidateConfirmation {
  const input = normalizeText(text).replace(/[。！？!?]+$/gu, "").trim();
  if (/^(?:确认|记下来|记下吧|好的|好|可以|安排上|就这样|嗯)$/u.test(input)) return "confirm";
  if (/^(?:取消|不用|不用记|不用了|别记|别提醒|不要|算了|不记)$/u.test(input)) return "cancel";
  return "other";
}

function cleanOperationTitle(value: string): string {
  return stripSentencePunctuation(value)
    .replace(/^(?:任务|待办)[：:、\s]*/u, "")
    .replace(/[「」“”"']/gu, "")
    .trim();
}

function createTaskOperation(
  operation: TaskOperationType,
  targetTitle: string,
  sourceMessageId: string,
  evidence: string,
  options: TaskExtractorOptions,
  timing?: ParsedTiming,
): TaskOperationCandidate {
  const timezoneOffsetMinutes = getTimezoneOffsetMinutes(options);
  const schedule = timing ? buildDueAt(timing, timezoneOffsetMinutes) : { dueAt: null, schedulePrecision: "date" as const };
  const needsConfirmation = Boolean(
    (operation === "postpone" || operation === "reschedule")
      && (!schedule.dueAt || timing?.timeAmbiguous),
  );
  return {
    operation,
    targetTitle: cleanOperationTitle(targetTitle),
    ...schedule,
    remindAt: timing?.time && !timing.time.ambiguous && schedule.dueAt ? schedule.dueAt : null,
    timezone: getTimezoneName(options),
    timezoneOffsetMinutes,
    sourceMessageId: sourceMessageId.trim(),
    evidence,
    explicitness: needsConfirmation ? "time_ambiguous" : "explicit",
    confidence: needsConfirmation ? 0.68 : 0.96,
    needsConfirmation,
    confirmationReason: needsConfirmation ? "新时间还不明确，需要确认后再修改任务。" : null,
  };
}

export function extractTaskOperation(
  text: string,
  sourceMessageId: string,
  options: TaskExtractorOptions = {},
): TaskOperationCandidate | null {
  const evidence = text.trim();
  const input = normalizeText(text);
  if (
    !input ||
    !sourceMessageId.trim() ||
    isSensitiveTaskInput(input) ||
    containsSensitiveCompanionText(evidence) ||
    containsSensitiveCompanionText(sourceMessageId)
  ) return null;
  if (NEGATED_EXPRESSION.test(input) || HYPOTHETICAL_EXPRESSION.test(input) || JOKING_EXPRESSION.test(input)) return null;

  const complete = input.match(/^(?:帮我\s*)?(?:完成|做完|标记完成)(?:任务)?[：:、\s]*(.+)$/u);
  if (complete) {
    const targetTitle = cleanOperationTitle(complete[1]);
    return targetTitle ? createTaskOperation("complete", targetTitle, sourceMessageId, evidence, options) : null;
  }
  const cancel = input.match(/^(?:帮我\s*)?取消(?:任务|待办)?[：:、\s]*(.+)$/u);
  if (cancel) {
    const targetTitle = cleanOperationTitle(cancel[1]);
    return targetTitle ? createTaskOperation("cancel", targetTitle, sourceMessageId, evidence, options) : null;
  }

  const postpone = input.match(/^(?:帮我\s*)?(延期|推迟|顺延)(?:任务|待办)?\s*(.+?)\s*(?:到|至)\s*(.+)$/u);
  if (postpone) {
    const timing = parseTaskTiming(postpone[3], options);
    return createTaskOperation("postpone", postpone[2], sourceMessageId, evidence, options, timing);
  }
  const reschedule = input.match(/^把\s*(.+?)\s*(?:改到|调整到|安排到|改为)\s*(.+)$/u);
  if (reschedule) {
    const timing = parseTaskTiming(reschedule[2], options);
    return createTaskOperation("reschedule", reschedule[1], sourceMessageId, evidence, options, timing);
  }
  return null;
}

export function normalizeTaskTitle(value: string): string {
  return value
    .toLocaleLowerCase()
    .replace(/[提醒记下任务待办]+/gu, "")
    .replace(/[\p{P}\p{S}\s]+/gu, "")
    .trim();
}

function titleSimilarity(left: string, right: string): number {
  const a = normalizeTaskTitle(left);
  const b = normalizeTaskTitle(right);
  if (!a || !b) return 0;
  if (a === b || a.includes(b) || b.includes(a)) return 1;
  const aChars = Array.from(a);
  const bChars = Array.from(b);
  const aBigrams = new Set(aChars.length > 1 ? aChars.slice(0, -1).map((_, index) => aChars.slice(index, index + 2).join("")) : aChars);
  const bBigrams = new Set(bChars.length > 1 ? bChars.slice(0, -1).map((_, index) => bChars.slice(index, index + 2).join("")) : bChars);
  const intersection = [...aBigrams].filter((value) => bBigrams.has(value)).length;
  return (2 * intersection) / (aBigrams.size + bBigrams.size);
}

export function areTaskTitlesSimilar(left: string, right: string): boolean {
  return titleSimilarity(left, right) >= 0.72;
}

function taskDueKey(task: Pick<Task, "dueAt" | "schedulePrecision">): string | null {
  if (!task.dueAt) return null;
  if (task.schedulePrecision === "date" || DATE_ONLY_PATTERN.test(task.dueAt)) return `date:${task.dueAt.slice(0, 10)}`;
  const timestamp = Date.parse(task.dueAt);
  return Number.isFinite(timestamp) ? `datetime:${Math.floor(timestamp / 60_000)}` : null;
}

export function taskCandidateDueKey(candidate: TaskCandidate): string | null {
  return taskDueKey(candidate);
}

export function getTaskCandidateDedupKey(candidate: TaskCandidate): string | null {
  const dueKey = taskCandidateDueKey(candidate);
  return dueKey ? `${normalizeTaskTitle(candidate.title)}|${dueKey}` : null;
}

function isActiveTask(task: Task): boolean {
  return !task.deletedAt && !["completed", "cancelled"].includes(task.status);
}

export function findDuplicateTask(
  database: TaskDatabase,
  candidate: TaskCandidate,
): Task | null {
  const candidateDueKey = taskCandidateDueKey(candidate);
  if (!candidateDueKey) return null;
  return database.tasks.find((task) =>
    isActiveTask(task)
      && taskDueKey(task) === candidateDueKey
      && areTaskTitlesSimilar(task.title, candidate.title),
  ) ?? null;
}

export function findTaskReference(
  database: TaskDatabase,
  targetTitle: string,
  includeTerminal = false,
): TaskReferenceMatch {
  const candidates = database.tasks.filter((task) => {
    if (task.deletedAt) return false;
    if (!includeTerminal && !isActiveTask(task)) return false;
    return areTaskTitlesSimilar(task.title, targetTitle);
  });
  if (!candidates.length) return { status: "not_found", task: null };
  const exact = candidates.filter((task) => normalizeTaskTitle(task.title) === normalizeTaskTitle(targetTitle));
  if (exact.length === 1) return { status: "found", task: exact[0] };
  if (candidates.length !== 1) return { status: "ambiguous", task: null };
  return { status: "found", task: candidates[0] };
}

export function getPendingTaskCandidateForPet(
  pending: PendingTaskCandidate | null,
  activePetId: string,
): TaskCandidate | null {
  return pending && pending.petId === activePetId ? pending.candidate : null;
}
