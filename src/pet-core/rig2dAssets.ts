export type Rig2dMeshData = {
  id: string;
  positions: number[][];
  uvs: number[][];
  indices: number[];
  drawOrder: number;
  texture: string | null;
  colourDetail?: { texture: string; sourceRectangle: number[]; sha256: string; baseSha256: string };
  mask: string;
  isClippingMask: boolean;
  clipping: { mask: string; mode: "inside" | "outside" } | null;
};
export type LoadedRig2dMesh = { data: Rig2dMeshData; textureUrl: string; detailTextureUrl?: string };

/** Resolve nested material references while retaining the package boundary. */
export function resolveRig2dAssetUrl(packageUrl: string, fromUrl: string, reference: string): string {
  const root = new URL(packageUrl);
  if (!root.pathname.endsWith("/")) throw new Error("Rig package URL must end in /");
  if (!reference || /[%:?#\\]/.test(reference) || reference.startsWith("/")) {
    throw new Error("Invalid rig asset reference");
  }
  const from = new URL(fromUrl);
  const result = new URL(reference, from);
  for (const url of [from, result]) {
    if (url.origin !== root.origin || !url.pathname.startsWith(root.pathname)) {
      throw new Error("Rig asset escapes package");
    }
  }
  return result.href;
}

export function validateRig2dMesh(value: unknown): asserts value is Rig2dMeshData {
  if (!value || typeof value !== "object") throw new Error("Invalid rig mesh");
  const m = value as Rig2dMeshData;
  const pairs = (v: unknown): v is number[][] => Array.isArray(v) && v.length > 0 && v.every(p =>
    Array.isArray(p) && p.length === 2 && p.every(Number.isFinite));
  if (typeof m.id !== "string" || !m.id || !pairs(m.positions) || !pairs(m.uvs) ||
      m.positions.length !== m.uvs.length || !Number.isFinite(m.drawOrder) ||
      !Array.isArray(m.indices) || !m.indices.length || m.indices.length % 3 !== 0 ||
      !m.indices.every(i => Number.isInteger(i) && i >= 0 && i < m.positions.length) ||
      !m.uvs.every(p => p.every(v => v >= 0 && v <= 1)) ||
      typeof m.mask !== "string" || typeof m.isClippingMask !== "boolean" ||
      (!m.isClippingMask && typeof m.texture !== "string")) throw new Error("Malformed rig geometry: " + m.id);
  if (m.colourDetail) {
    const d=m.colourDetail,r=d.sourceRectangle;
    if (m.isClippingMask || typeof d.texture!=="string" || !Array.isArray(r) || r.length!==4 || !r.every(Number.isFinite) || r[0]<0 || r[1]<0 || r[2]<=r[0] || r[3]<=r[1] || !/^[a-f0-9]{64}$/.test(d.sha256) || !/^[a-f0-9]{64}$/.test(d.baseSha256)) throw new Error("Invalid rig colour detail");
  }
  if (m.clipping && (typeof m.clipping.mask !== "string" || !["inside", "outside"].includes(m.clipping.mode))) {
    throw new Error("Invalid rig clipping");
  }
  for (let i = 0; i < m.indices.length; i += 3) {
    for (const coordinates of [m.positions, m.uvs]) {
      const [a, b, c] = m.indices.slice(i, i + 3).map(j => coordinates[j]);
      if ((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]) <= 0) throw new Error("Folded rig triangle");
    }
  }
}

export async function loadRig2dMeshes(packageUrl: string, contractUrl: string, signal?: AbortSignal): Promise<{ canvas: number[]; meshes: LoadedRig2dMesh[] }> {
  const read = async (url: string): Promise<unknown> => {
    const response = await fetch(url, { signal });
    if (!response.ok) throw new Error(`Rig fetch failed: ${response.status}`);
    return response.json();
  };
  resolveRig2dAssetUrl(packageUrl, contractUrl, "./");
  const contract = await read(contractUrl) as { canvas: number[]; meshes: { id: string; path: string }[] };
  if (!Array.isArray(contract.canvas) || contract.canvas.length !== 2 || !contract.canvas.every(n => Number.isInteger(n) && n > 0 && n <= 8192) ||
      !Array.isArray(contract.meshes) || !contract.meshes.length) throw new Error("Invalid rig contract");
  const meshes = await Promise.all(contract.meshes.map(async entry => {
    const url = resolveRig2dAssetUrl(packageUrl, contractUrl, entry.path);
    const data = await read(url); validateRig2dMesh(data);
    if (data.id !== entry.id) throw new Error("Rig mesh identity mismatch");
    const textureUrl=resolveRig2dAssetUrl(packageUrl,url,data.isClippingMask?data.mask:data.texture!);
    let detailTextureUrl: string | undefined;
    if (data.colourDetail) {
      const detail=data.colourDetail;
      if(detail.sourceRectangle[2]>contract.canvas[0] || detail.sourceRectangle[3]>contract.canvas[1])throw new Error("Rig detail outside canvas");
      detailTextureUrl=resolveRig2dAssetUrl(packageUrl,url,detail.texture);
      for(const [asset,expected] of [[textureUrl,detail.baseSha256],[detailTextureUrl,detail.sha256]]){
        const response=await fetch(asset,{signal});if(!response.ok)throw new Error("Rig colour input missing");
        const digest=await crypto.subtle.digest("SHA-256",await response.arrayBuffer());
        const hash=Array.from(new Uint8Array(digest),v=>v.toString(16).padStart(2,"0")).join("");
        if(hash!==expected)throw new Error("Rig colour input version mismatch");
      }
    }
    return {data,textureUrl,detailTextureUrl};
  }));
  const ids = new Map(meshes.map(m => [m.data.id, m.data]));
  if (ids.size !== meshes.length) throw new Error("Duplicate rig material");
  for (const { data } of meshes) if (data.clipping && !ids.get(data.clipping.mask)?.isClippingMask) throw new Error("Missing rig mask");
  return { canvas: contract.canvas, meshes };
}
