export type AccountPetMood = "idle" | "email" | "password";

export type NormalizedPointer = { x: number; y: number };

export type AccountPetParameters = {
  angleX: number;
  angleY: number;
  angleZ: number;
  eyeBallX: number;
  eyeBallY: number;
  eyeOpen: number;
  mouthForm: number;
  pawCover: number;
};

export const ACCOUNT_PET_PARAMETER_IDS = {
  angleX: "ParamAngleX",
  angleY: "ParamAngleY",
  angleZ: "ParamAngleZ",
  eyeBallX: "ParamEyeBallX",
  eyeBallY: "ParamEyeBallY",
  eyeLeftOpen: "ParamEyeLOpen",
  eyeRightOpen: "ParamEyeROpen",
  mouthForm: "ParamMouthForm",
  pawLeftCover: "ParamEyeLSmile",
  pawRightCover: "ParamEyeRSmile",
} as const;

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(max, value));

export function getAccountPetTargetParameters(
  mood: AccountPetMood,
  pointer: NormalizedPointer,
): AccountPetParameters {
  const x = clamp(pointer.x, -1, 1);
  const y = clamp(pointer.y, -1, 1);

  if (mood === "password") {
    return {
      angleX: 0,
      angleY: 4,
      angleZ: 0,
      eyeBallX: 0,
      eyeBallY: 0,
      eyeOpen: 0,
      mouthForm: .45,
      pawCover: 1,
    };
  }

  const emailBias = mood === "email" ? .55 : 0;
  return {
    angleX: clamp((x * 10) + (emailBias * 8), -12, 14),
    angleY: clamp(y * -7, -8, 8),
    angleZ: mood === "email" ? -6 : x * -1.5,
    eyeBallX: clamp((x * .72) + emailBias, -1, 1),
    eyeBallY: clamp(y * -.6, -1, 1),
    eyeOpen: 1,
    mouthForm: mood === "email" ? .8 : .25,
    pawCover: 0,
  };
}

export function dampAccountPetParameters(
  current: AccountPetParameters,
  target: AccountPetParameters,
  deltaMs: number,
  response = 9,
): AccountPetParameters {
  const alpha = 1 - Math.exp(-response * Math.max(0, deltaMs) / 1000);
  return Object.fromEntries(
    Object.entries(current).map(([key, value]) => [
      key,
      value + ((target[key as keyof AccountPetParameters] - value) * alpha),
    ]),
  ) as AccountPetParameters;
}
