import { describe, expect, test, vi } from "vitest";
import {
  choosePetSoundCue,
  createPetSoundPlayer,
  getPetSoundCooldownMs,
  resolvePetSoundCues,
  type PetAudioElement,
} from "./sound";

type TestMock<T extends (...args: never[]) => unknown> = T & {
  mock: { calls: unknown[][] };
};

type FakeAudio = PetAudioElement & {
  url: string;
  load: TestMock<() => void>;
  pause: TestMock<() => void>;
  play: TestMock<() => Promise<void>>;
};

function createFakeAudioFactory(created: FakeAudio[]) {
  return (url: string): FakeAudio => {
    const audio: FakeAudio = {
      url,
      preload: "",
      volume: 1,
      currentTime: 9,
      load: vi.fn(() => undefined) as TestMock<() => void>,
      pause: vi.fn(() => undefined) as TestMock<() => void>,
      play: vi.fn(() => Promise.resolve()) as TestMock<() => Promise<void>>,
    };

    created.push(audio);
    return audio;
  };
}

describe("pet sound rules", () => {
  test("resolves sound cue URLs under the active pet package", () => {
    expect(
      resolvePetSoundCues(
        "xiaoju-cat",
        {
          tickle: [
            { path: "sounds/tickle-hm-1.wav", volume: 0.45 },
            { path: "" },
          ],
        },
        "tickle",
      ),
    ).toEqual([
      {
        path: "sounds/tickle-hm-1.wav",
        volume: 0.45,
        url: "/pets/xiaoju-cat/sounds/tickle-hm-1.wav",
      },
    ]);
  });

  test("chooses a deterministic random cue", () => {
    const cues = [
      { path: "sounds/a.wav", url: "/pets/xiaoju-cat/sounds/a.wav" },
      { path: "sounds/b.wav", url: "/pets/xiaoju-cat/sounds/b.wav" },
      { path: "sounds/c.wav", url: "/pets/xiaoju-cat/sounds/c.wav" },
    ];

    expect(choosePetSoundCue(cues, () => 0)?.path).toBe("sounds/a.wav");
    expect(choosePetSoundCue(cues, () => 0.5)?.path).toBe("sounds/b.wav");
    expect(choosePetSoundCue(cues, () => 0.99)?.path).toBe("sounds/c.wav");
    expect(choosePetSoundCue([], () => 0.5)).toBeNull();
  });

  test("preloads all manifest sounds when the active pet changes", () => {
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
    });

    player.setManifest("xiaoju-cat", {
      tickle: [
        { path: "sounds/tickle-hm-1.wav" },
        { path: "sounds/tickle-hmph-1.wav" },
      ],
      drag: [{ path: "sounds/drag-meow-1.wav" }],
    });

    expect(created.map((audio) => audio.url)).toEqual([
      "/pets/xiaoju-cat/sounds/tickle-hm-1.wav",
      "/pets/xiaoju-cat/sounds/tickle-hmph-1.wav",
      "/pets/xiaoju-cat/sounds/drag-meow-1.wav",
    ]);
    expect(created.every((audio) => audio.preload === "auto")).toBe(true);
    expect(created.every((audio) => audio.load.mock.calls.length === 1)).toBe(
      true,
    );
  });

  test("plays one cue, applies volume, respects cooldown, and interrupts active sound", () => {
    const created: FakeAudio[] = [];
    let now = 1000;
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
      random: () => 0.99,
      now: () => now,
      masterVolume: 0.5,
    });

    player.setManifest("xiaoju-cat", {
      tickle: [
        { path: "sounds/tickle-hm-1.wav", volume: 0.4 },
        { path: "sounds/tickle-hmph-1.wav", volume: 0.6 },
      ],
    });

    expect(player.play("tickle")).toBe(true);
    expect(created[1].currentTime).toBe(0);
    expect(created[1].volume).toBe(0.3);
    expect(created[1].play).toHaveBeenCalledTimes(1);

    now += 100;
    expect(player.play("tickle")).toBe(false);
    expect(created[1].play).toHaveBeenCalledTimes(1);

    now += getPetSoundCooldownMs("tickle");
    expect(player.play("tickle")).toBe(true);
    expect(created[1].pause).toHaveBeenCalledTimes(1);
    expect(created[1].play).toHaveBeenCalledTimes(2);
  });

  test("skips playback when disabled or when an event has no cues", () => {
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
    });

    player.setManifest("xiaoju-cat", {
      tickle: [{ path: "sounds/tickle-hm-1.wav" }],
    });
    player.setEnabled(false);

    expect(player.play("tickle")).toBe(false);
    player.setEnabled(true);
    expect(player.play("missing")).toBe(false);
  });

  test("handles rejected browser audio playback without throwing", () => {
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: (url) => {
        const audio = createFakeAudioFactory(created)(url);
        audio.play = vi.fn(() =>
          Promise.reject(new Error("blocked")),
        ) as TestMock<() => Promise<void>>;
        return audio;
      },
    });

    player.setManifest("xiaoju-cat", {
      tickle: [{ path: "sounds/tickle-hm-1.wav" }],
    });

    expect(() => player.play("tickle")).not.toThrow();
  });

  test("stops long cues after their configured maximum duration", () => {
    vi.useFakeTimers();
    const created: FakeAudio[] = [];
    const player = createPetSoundPlayer({
      audioFactory: createFakeAudioFactory(created),
    });

    try {
      player.setManifest("xiaoju-cat", {
        idle: [{ path: "sounds/purr-whiskers.ogg", maxDurationMs: 800 }],
      });

      expect(player.play("idle")).toBe(true);
      expect(created[0].pause).not.toHaveBeenCalled();

      vi.advanceTimersByTime(799);
      expect(created[0].pause).not.toHaveBeenCalled();

      vi.advanceTimersByTime(1);
      expect(created[0].pause).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
