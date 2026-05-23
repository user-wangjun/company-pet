export interface UpdateManifest {
  version: string;
  downloadUrl?: string;
  notes?: string;
}

export type UpdateStatus =
  | {
      kind: 'not-configured';
      currentVersion: string;
    }
  | {
      kind: 'available';
      currentVersion: string;
      latestVersion: string;
      downloadUrl?: string;
      notes?: string;
    }
  | {
      kind: 'current';
      currentVersion: string;
      latestVersion: string;
    }
  | {
      kind: 'unavailable';
      currentVersion: string;
    };

export interface CheckForAppUpdateInput {
  currentVersion: string;
  manifestUrl?: string;
  fetcher?: typeof fetch;
}

export async function checkForAppUpdate(input: CheckForAppUpdateInput): Promise<UpdateStatus> {
  const manifestUrl = input.manifestUrl?.trim();
  if (!manifestUrl) {
    return { kind: 'not-configured', currentVersion: input.currentVersion };
  }

  try {
    const response = await (input.fetcher ?? fetch)(manifestUrl, { cache: 'no-store' });
    if (!response.ok) {
      return { kind: 'unavailable', currentVersion: input.currentVersion };
    }

    const manifest = (await response.json()) as Partial<UpdateManifest>;
    if (!manifest.version) {
      return { kind: 'unavailable', currentVersion: input.currentVersion };
    }

    if (isVersionGreater(manifest.version, input.currentVersion)) {
      return {
        kind: 'available',
        currentVersion: input.currentVersion,
        latestVersion: manifest.version,
        downloadUrl: manifest.downloadUrl,
        notes: manifest.notes,
      };
    }

    return {
      kind: 'current',
      currentVersion: input.currentVersion,
      latestVersion: manifest.version,
    };
  } catch {
    return { kind: 'unavailable', currentVersion: input.currentVersion };
  }
}

function isVersionGreater(candidate: string, current: string) {
  const candidateParts = parseVersion(candidate);
  const currentParts = parseVersion(current);
  const length = Math.max(candidateParts.length, currentParts.length);

  for (let index = 0; index < length; index += 1) {
    const candidatePart = candidateParts[index] ?? 0;
    const currentPart = currentParts[index] ?? 0;
    if (candidatePart > currentPart) {
      return true;
    }
    if (candidatePart < currentPart) {
      return false;
    }
  }

  return false;
}

function parseVersion(version: string) {
  return version
    .split(/[.-]/)
    .map((part) => Number.parseInt(part, 10))
    .map((part) => (Number.isFinite(part) ? part : 0));
}
