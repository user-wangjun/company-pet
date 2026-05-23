import { describe, expect, it } from 'vitest';
import { checkForAppUpdate } from './updateService';

describe('checkForAppUpdate', () => {
  it('reports a reserved update interface when no manifest URL is configured', async () => {
    await expect(
      checkForAppUpdate({
        currentVersion: '0.1.0',
        manifestUrl: '',
      }),
    ).resolves.toMatchObject({
      kind: 'not-configured',
      currentVersion: '0.1.0',
    });
  });

  it('detects a newer version from the update manifest', async () => {
    await expect(
      checkForAppUpdate({
        currentVersion: '0.1.0',
        manifestUrl: 'https://updates.example.com/xiaoju.json',
        fetcher: async () =>
          new Response(
            JSON.stringify({
              version: '0.2.0',
              downloadUrl: 'https://updates.example.com/xiaoju-0.2.0.exe',
              notes: '新增桌面感知。',
            }),
          ),
      }),
    ).resolves.toEqual({
      kind: 'available',
      currentVersion: '0.1.0',
      latestVersion: '0.2.0',
      downloadUrl: 'https://updates.example.com/xiaoju-0.2.0.exe',
      notes: '新增桌面感知。',
    });
  });

  it('treats the current version as up to date', async () => {
    await expect(
      checkForAppUpdate({
        currentVersion: '0.2.0',
        manifestUrl: 'https://updates.example.com/xiaoju.json',
        fetcher: async () => new Response(JSON.stringify({ version: '0.2.0' })),
      }),
    ).resolves.toMatchObject({
      kind: 'current',
      currentVersion: '0.2.0',
      latestVersion: '0.2.0',
    });
  });

  it('returns unavailable when the update manifest cannot be read', async () => {
    await expect(
      checkForAppUpdate({
        currentVersion: '0.1.0',
        manifestUrl: 'https://updates.example.com/xiaoju.json',
        fetcher: async () => new Response('', { status: 503 }),
      }),
    ).resolves.toMatchObject({
      kind: 'unavailable',
      currentVersion: '0.1.0',
    });
  });
});
