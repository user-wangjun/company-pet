/**
 * These patterns intentionally describe categories as well as recognizable
 * credential shapes. User-controlled text must fail closed at every domain
 * boundary, even when it does not use a friendly label such as "password".
 */
const SENSITIVE_CREDENTIAL_PATTERNS: readonly RegExp[] = [
  /-----BEGIN\s+(?:[A-Z]+\s+)?PRIVATE\s+KEY-----/iu,
  /\b(?:sk|rk|pk|ghp|github_pat|xox[baprs])[_-][A-Za-z0-9][A-Za-z0-9_-]{7,}\b/iu,
  /\bAIza[A-Za-z0-9_-]{20,}\b/u,
  /\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b/iu,
  /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/u,
  /(?:^|[^\d])\d{3}[- ]\d{2}[- ]\d{4}(?:$|[^\d])/u,
  /(?:^|[^\d])\d{17}[\dXx](?:$|[^\d])/u,
  /(?:^|[^\d])\d{13,19}(?:$|[^\d])/u,
];

const SENSITIVE_CATEGORY_PATTERNS: readonly RegExp[] = [
  /(?:密码|口令|支付密码|登录密码|password|passcode|passphrase|passwd|pwd)/iu,
  /(?:令牌|token|access[_ -]?token|refresh[_ -]?token|bearer)/iu,
  /(?:api\s*[_ -]?key|apikey|api[_ -]?密钥|密钥)/iu,
  /(?:私钥|私密钥|private\s+key|ssh\s+key)/iu,
  /(?:身份证(?:号|号码)?|公民身份号码|social security number|\bssn\b|national id(?:entity)?|identity card|id number)/iu,
  /(?:银行卡(?:号)?|银行账号|信用卡(?:号)?|借记卡|账号|护照|社保|passport|bank card|debit card|credit card|card number|bank account(?: number)?|routing number)/iu,
  /(?:精确地址|详细地址|家庭住址|家庭地址|联系地址|住址|exact address|full address|precise address|street address|home address|residential address|mailing address)/iu,
  /(?:我的地址|我的住址|我住在|我居住在|住在|my address|my home address|i live at|i'm at|im at)\s*(?:是|为|在|is|at)?\s*[^\s,，。；;]{3,}/iu,
  /(?:地址|\baddress\b)\s*(?:是|为|在|[:=：]|is|at)\s*/iu,
  /(?:医疗诊断|诊断(?:结果)?|病史|医疗记录|健康记录|用药|吃药|药物|处方|病情|疾病史|治疗|\bdiagnosis\b|\bmedical history\b|\bmedical record\b|\bmedication(?:s)?\b|\bprescription\b|\bdiagnosed with\b|\bhealth condition\b|\btreatment\b)/iu,
];

// Profile values have a narrower final-pass detector than general chat text.
// Field/category allowlists remain the primary boundary; these shapes are only
// a last line of defence for a value that reached an otherwise allowed slot.
const COMPANION_PROFILE_EMAIL_PATTERN = /[^\s@,，；;]+@[^\s@,，；;]+\.[^\s@,，；;]+/u;
const COMPANION_PROFILE_PHONE_PATTERN = /(?:^|[^\d])(\+?[0-9][0-9\s().-]{5,22})(?:$|[^\d])/u;
const COMPANION_PROFILE_GENDER_PATTERN = /(?:^|[\s,，:：=])(?:unspecified|female|male|non-binary|prefer-not-to-say)(?:$|[\s,，:：=])/iu;

const SENSITIVE_LABEL_WITH_VALUE_PATTERNS: readonly RegExp[] = [
  /(?:我的|本人的|用户的|我有|my|my own|the user's|their)?\s*(?:密码|口令|password|passcode|passphrase|passwd|pwd|token|令牌|api\s*[_ -]?key|apikey|密钥|私钥|private\s+key)\s*(?:是|为|叫做|[:=：]|is|are|equals?)\s*[^\s,，。；;]+/iu,
  /(?:身份证(?:号|号码)?|公民身份号码|social security number|\bssn\b|national id(?:entity)?|identity card|id number)\s*(?:是|为|叫做|号码是|[:=：]|is|number is)?\s*[0-9xX][0-9xX\s-]{2,}/iu,
  /(?:银行卡(?:号)?|银行账号|信用卡(?:号)?|借记卡|bank card|debit card|credit card|card number|bank account(?: number)?|routing number)\s*(?:是|为|号码是|[:=：]|is|number is)?\s*[0-9][0-9\s-]{3,}/iu,
  /(?:(?:我的|本人的|我住在|用户的|my|my own|i live at|i'm at|im at|home|street|residential|mailing)?\s*(?:精确地址|详细地址|家庭住址|家庭地址|联系地址|住址|exact address|full address|precise address|street address|home address|residential address|mailing address|address))\s*(?:是|为|在|[:=：]|is|at)?\s*[^\n,，。；;、]{3,}/iu,
  /(?:我的|本人的|用户的|我有|my|my own|the user's|their)\s*(?:医疗诊断|诊断(?:结果)?|病史|医疗记录|健康记录|用药|吃药|药物|处方|病情|疾病史|治疗|diagnosis|medical history|medical record|medication(?:s)?|prescription|health condition|treatment)\s*(?:是|为|叫做|[:=：]|is|are|equals?)?\s*[^\n,，。；;]{2,}/iu,
  /(?:医疗诊断|诊断(?:结果)?|病史|医疗记录|健康记录|用药|吃药|药物|处方|病情|疾病史|治疗|\bdiagnosis\b|\bmedical history\b|\bmedical record\b|\bmedication(?:s)?\b|\bprescription\b|\bhealth condition\b|\btreatment\b)\s*(?:是|为|叫做|[:=：]|is|are|equals?)\s*[^\n,，。；;、]{2,}/iu,
];

const HEALTH_TERM_PATTERNS: readonly RegExp[] = [
  /(?:糖尿病|高血压|低血压|哮喘|偏头痛|抑郁症|焦虑症|心脏病|冠心病|癌症|肿瘤|癫痫|过敏|感染|炎症|失眠|骨折|结石|综合征|障碍|疾病|病史|病情|病症)/u,
  /\b(?:diabetes|asthma|migraine|hypertension|depression|anxiety|cancer|tumou?r|epilepsy|allerg(?:y|ies)|infection|insomnia|fracture|disease|disorder|syndrome|condition|illness|(?:[a-z]+)(?:itis|osis|emia|opathy))\b/iu,
];

const HEALTH_ASSERTION_PATTERNS: readonly RegExp[] = [
  /(?:我|本人)(?:目前|最近|一直|曾经|有点)?\s*(?:有|患有|得了|得过|被确诊为|确诊为|被诊断为|诊断为|正在治疗)\s*[^\n，,。；;!?]{1,40}/u,
  /\b(?:i|we)\s+(?:have|has|was diagnosed with|am diagnosed with|live with|suffer(?:s)? from)\s+(?!a\s+(?:question|query|meeting|call|plan|problem)\b)[^\n,.!?]{2,60}/iu,
  /\b(?:my|the patient's?)\s+(?:diagnosis|medical history|medical record|health condition)\s+(?:is|includes|says|shows|involves)\s+[^\n,.!?]{2,60}/iu,
  /\b(?:diagnosed with|medical diagnosis is|health condition is)\s+[^\n,.!?]{2,60}/iu,
];

const MEDICATION_NAME_PATTERNS: readonly RegExp[] = [
  /\bmetformin\b/iu,
  /[\u4e00-\u9fff]{2,12}(?:胍|霉素|西林|沙坦|他汀|洛尔|普利|拉唑|唑|昔布|替尼|单抗|胶囊|片剂)/u,
  /\b[a-z][a-z0-9-]{3,}(?:formin|cillin|mycin|pril|sartan|statin|olol|azole|vir|mab|nib|cycline)\b/iu,
];

const MEDICATION_USE_PATTERNS: readonly RegExp[] = [
  /(?:我|本人)(?:通常|每天|每日|正在|长期|需要)?\s*(?:吃|服用|用|吃药|服药|用药)\s*[^\n，,。；;!?]{0,40}/u,
  /\b(?:i|we)\s+(?:take|am taking|use|am using|am on)\s+[^\n,.!?]{2,60}/iu,
  /\b(?:my|the)\s+(?:medication|medicine|prescription|drug|pill|tablet|capsule|dose)\b[^\n,.!?]{0,60}/iu,
];

const CHINESE_ADDRESS_SHAPE = /[\u4e00-\u9fff]{2,}(?:省|市|自治区|特别行政区)?[\u4e00-\u9fff]{2,}(?:区|县|镇|乡|街道)[\u4e00-\u9fff]{1,16}(?:路|街|巷|道|胡同)\s*\d{1,5}\s*(?:号|弄|栋|幢|单元|室)?/u;
const ENGLISH_ADDRESS_SHAPE = /\b\d{1,6}\s+[A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,4}\s+(?:Street|St\.?|Road|Rd\.?|Avenue|Ave\.?|Lane|Ln\.?|Drive|Dr\.?|Boulevard|Blvd\.?|Court|Ct\.?|Way|Place|Pl\.?)\b(?:\s*,\s*[A-Za-z][A-Za-z .'-]+)?/iu;

const DISCUSSION_PATTERNS: readonly RegExp[] = [
  /密码(?:策略|政策|规范|安全|管理)/iu,
  /(?:医疗|医学|健康)(?:科普|教育|知识|讨论)/iu,
  /(?:讨论|科普|教育|政策|策略|规范|什么是|如何保护|怎么保护|为什么不能|不要把|不应把|不能把|不要发送|不要保存)/iu,
  /\b(?:password policy|security policy|medical education|health education|what is|how to protect|explain|discuss|policy|strategy|best practices)\b/iu,
];

export const SENSITIVE_COMPANION_PERSISTENCE_ERROR =
  "这类敏感内容不能保存到偏好、记忆或待办里。";

export const REMOTE_SENSITIVE_INPUT_REPLY =
  "这类隐私我们先不发到云端，好吗？我可以安静陪着你。";

/**
 * Final-pass detector for user-profile-shaped values. It intentionally does
 * not classify ordinary conversation such as "female" as globally sensitive;
 * callers use it only after a profile/preference field has passed its exact
 * projection allowlist.
 */
export function containsSensitiveCompanionProfileValue(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) return false;
  if (COMPANION_PROFILE_EMAIL_PATTERN.test(normalized)) return true;
  const phoneMatch = COMPANION_PROFILE_PHONE_PATTERN.exec(normalized);
  if (phoneMatch?.[1]) {
    const digits = phoneMatch[1].replace(/\D/gu, "");
    if (digits.length >= 7 && digits.length <= 20) return true;
  }
  return COMPANION_PROFILE_GENDER_PATTERN.test(normalized);
}

function matchesAny(value: string, patterns: readonly RegExp[]): boolean {
  return patterns.some((pattern) => pattern.test(value));
}

function hasHealthData(value: string): boolean {
  return matchesAny(value, HEALTH_ASSERTION_PATTERNS)
    && matchesAny(value, HEALTH_TERM_PATTERNS);
}

function hasMedicationData(value: string): boolean {
  if (!matchesAny(value, MEDICATION_USE_PATTERNS)) return false;
  return matchesAny(value, MEDICATION_NAME_PATTERNS)
    || /(?:吃药|服药|用药|药物|处方|\bmedication(?:s)?\b|\bmedicine\b|\bprescription\b|\bdrug\b|\bpill\b|\btablet\b|\bcapsule\b|\bdose\b)/iu.test(value);
}

function hasStructuredSensitiveData(value: string): boolean {
  return matchesAny(value, SENSITIVE_CREDENTIAL_PATTERNS)
    || matchesAny(value, SENSITIVE_LABEL_WITH_VALUE_PATTERNS)
    || hasHealthData(value)
    || hasMedicationData(value)
    // Both address shapes require a house number. Avoid sending a long
    // number-free CJK reply through the backtracking-heavy shape matcher.
    // This keeps the privacy boundary fail-closed without turning a valid
    // ordinary 2,000-character reply into a multi-second operation.
    || (/[0-9]/u.test(value)
      && (CHINESE_ADDRESS_SHAPE.test(value) || ENGLISH_ADDRESS_SHAPE.test(value)));
}

function isDiscussionWithoutAttachedData(value: string): boolean {
  return matchesAny(value, DISCUSSION_PATTERNS) && !hasStructuredSensitiveData(value);
}

/**
 * Conservative detector for untrusted user-controlled context fields.
 * A whole field/message is excluded when this returns true.
 */
export function containsSensitiveCompanionText(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) return false;
  if (isDiscussionWithoutAttachedData(normalized)) return false;
  return matchesAny(normalized, SENSITIVE_CATEGORY_PATTERNS)
    || hasStructuredSensitiveData(normalized);
}

/**
 * Narrower detector used for already-assembled trusted policy text. It looks
 * for a value attached to a sensitive label, not merely a policy mention of a
 * category such as “password” or “medical history”.
 */
export function containsSensitiveCompanionData(value: string): boolean {
  const normalized = value.trim();
  if (!normalized) return false;
  return hasStructuredSensitiveData(normalized);
}

export function removeSensitiveCompanionDataLines(value: string): string {
  return value
    .split(/\r?\n/)
    .filter((line) => !containsSensitiveCompanionData(line))
    .join("\n")
    .trim();
}
