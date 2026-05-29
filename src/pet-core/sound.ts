import {
  resolvePetAssetUrl,
  type PetManifestSounds,
  type PetSoundCue,
} from "./petAssets";

export const PET_SOUND_DEFAULT_VOLUME = 0.45;
export const PET_SOUND_DEFAULT_COOLDOWN_MS = 1200;

const PET_SOUND_COOLDOWNS_MS: Record<string, number> = {
  idle: 30000,
  tickle: 1200,
  drag: 2000,
  drag_end: 1200,
  fishChase: 1200,
  fishEat: 1200,
  crouchAlert: 2500,
  hugFish: 2500,
  gnawFish: 2500,
  iconHug: 2500,
  care_reminder: 5000,
};

export type PetSoundEvent =
  | "idle"
  | "tickle"
  | "drag"
  | "drag_end"
  | "fishChase"
  | "fishEat"
  | "crouchAlert"
  | "hugFish"
  | "gnawFish"
  | "iconHug"
  | "care_reminder";

export type ResolvedPetSoundCue = PetSoundCue & {
  url: string;
};

export type PetAudioElement = {
  preload: string;
  volume: number;
  currentTime: number;
  load?: () => void;
  pause: () => void;
  play: () => Promise<void> | void;
};

type PetSoundPlayerOptions = {
  audioFactory?: (url: string) => PetAudioElement;
  random?: () => number;
  now?: () => number;
  masterVolume?: number;
  enabled?: boolean;
};

export type PetSoundPlayer = {
  setManifest: (petId: string, sounds: PetManifestSounds | undefined) => void;
  setEnabled: (nextEnabled: boolean) => void;
  setMasterVolume: (nextVolume: number) => void;
  play: (eventName: string) => boolean;
  clear: () => void;
};

function defaultAudioFactory(url: string): PetAudioElement {
  return new Audio(url);
}

export function getPetSoundCooldownMs(eventName: string): number {
  return PET_SOUND_COOLDOWNS_MS[eventName] ?? PET_SOUND_DEFAULT_COOLDOWN_MS;
}

export function clampPetSoundVolume(volume: number | undefined): number {
  if (volume === undefined || !Number.isFinite(volume)) {
    return PET_SOUND_DEFAULT_VOLUME;
  }

  return Math.min(1, Math.max(0, volume));
}

export function resolvePetSoundCues(
  petId: string,
  sounds: PetManifestSounds | undefined,
  eventName: string,
): ResolvedPetSoundCue[] {
  return (sounds?.[eventName] ?? [])
    .filter((cue) => cue.path.trim().length > 0)
    .map((cue) => ({
      ...cue,
      url: resolvePetAssetUrl(petId, cue.path),
    }));
}

export function choosePetSoundCue(
  cues: ResolvedPetSoundCue[],
  random = Math.random,
): ResolvedPetSoundCue | null {
  if (cues.length === 0) return null;

  const index = Math.min(cues.length - 1, Math.floor(random() * cues.length));
  return cues[index] ?? cues[0];
}

export function createPetSoundPlayer({
  audioFactory = defaultAudioFactory,
  random = Math.random,
  now = Date.now,
  masterVolume: initialMasterVolume = 1,
  enabled: initialEnabled = true,
}: PetSoundPlayerOptions = {}): PetSoundPlayer {
  let petId = "";
  let sounds: PetManifestSounds | undefined;
  let enabled = initialEnabled;
  let masterVolume = clampPetSoundVolume(initialMasterVolume);
  let activeAudio: PetAudioElement | null = null;
  let activeStopTimer: ReturnType<typeof setTimeout> | null = null;

  const audioByUrl = new Map<string, PetAudioElement>();
  const lastPlayedAtByEvent = new Map<string, number>();

  const getAudio = (cue: ResolvedPetSoundCue): PetAudioElement => {
    const cached = audioByUrl.get(cue.url);
    if (cached) return cached;

    const audio = audioFactory(cue.url);
    audio.preload = "auto";
    audio.volume = clampPetSoundVolume(cue.volume) * masterVolume;
    audio.load?.();
    audioByUrl.set(cue.url, audio);
    return audio;
  };

  const stopActiveAudio = () => {
    if (activeStopTimer !== null) {
      clearTimeout(activeStopTimer);
      activeStopTimer = null;
    }
    if (!activeAudio) return;
    activeAudio.pause();
    activeAudio = null;
  };

  return {
    setManifest(nextPetId, nextSounds) {
      stopActiveAudio();
      audioByUrl.clear();
      lastPlayedAtByEvent.clear();
      petId = nextPetId;
      sounds = nextSounds;

      if (!sounds) return;

      for (const eventName of Object.keys(sounds)) {
        for (const cue of resolvePetSoundCues(petId, sounds, eventName)) {
          getAudio(cue);
        }
      }
    },

    setEnabled(nextEnabled) {
      enabled = nextEnabled;
      if (!enabled) {
        stopActiveAudio();
      }
    },

    setMasterVolume(nextVolume) {
      masterVolume = clampPetSoundVolume(nextVolume);
    },

    play(eventName) {
      if (!enabled || !petId) return false;

      const playedAt = now();
      const lastPlayedAt = lastPlayedAtByEvent.get(eventName);
      if (
        lastPlayedAt !== undefined &&
        playedAt - lastPlayedAt < getPetSoundCooldownMs(eventName)
      ) {
        return false;
      }

      const cue = choosePetSoundCue(
        resolvePetSoundCues(petId, sounds, eventName),
        random,
      );
      if (!cue) return false;

      const audio = getAudio(cue);
      stopActiveAudio();

      audio.currentTime = 0;
      audio.volume = clampPetSoundVolume(cue.volume) * masterVolume;
      activeAudio = audio;
      lastPlayedAtByEvent.set(eventName, playedAt);

      try {
        const result = audio.play();
        if (result instanceof Promise) {
          result.catch(() => {});
        }
      } catch {
        // Browser audio can be blocked by policy; animation should continue.
      }

      if (
        cue.maxDurationMs !== undefined &&
        Number.isFinite(cue.maxDurationMs) &&
        cue.maxDurationMs > 0
      ) {
        activeStopTimer = setTimeout(() => {
          if (activeAudio !== audio) return;
          audio.pause();
          activeAudio = null;
          activeStopTimer = null;
        }, cue.maxDurationMs);
      }

      return true;
    },

    clear() {
      stopActiveAudio();
      audioByUrl.clear();
      lastPlayedAtByEvent.clear();
      petId = "";
      sounds = undefined;
    },
  };
}
