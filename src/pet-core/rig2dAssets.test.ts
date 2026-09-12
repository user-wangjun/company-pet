import { describe, expect, test, vi, afterEach } from "vitest";
import { loadRig2dMeshes, resolveRig2dAssetUrl, validateRig2dMesh } from "./rig2dAssets";
const root="https://pet.test/pets/sample/",from=root+"model/meshes/face.json";
const mesh=()=>({id:"face",positions:[[0,0],[1,0],[0,1]],uvs:[[0,0],[1,0],[0,1]],indices:[0,1,2],drawOrder:1,texture:"../textures/face.png",mask:"../masks/face.png",isClippingMask:false,clipping:null});
afterEach(()=>vi.unstubAllGlobals());
describe("rig package loading",()=>{
 test("resolves nested references within the package",()=>expect(resolveRig2dAssetUrl(root,from,"../textures/face.png")).toBe(root+"model/textures/face.png"));
 test.each(["../../../other.png","/secret","https://other.test/a","%2e%2e/a","..\\a","a?secret"])("rejects unsafe reference %s",ref=>expect(()=>resolveRig2dAssetUrl(root,from,ref)).toThrow());
 test("rejects out-of-range indices and reversed UVs",()=>{
  expect(()=>validateRig2dMesh({...mesh(),indices:[0,1,3]})).toThrow();
  expect(()=>validateRig2dMesh({...mesh(),uvs:[[0,0],[0,1],[1,0]]})).toThrow();
 });
 test("rejects a dangling clipping mask after loading",async()=>{
  vi.stubGlobal("fetch",vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({canvas:[512,1086],meshes:[{id:"face",path:"meshes/face.json"}]})}).mockResolvedValueOnce({ok:true,json:async()=>({...mesh(),clipping:{mask:"missing",mode:"inside"}})}));
  await expect(loadRig2dMeshes(root,root+"model/rig.json")).rejects.toThrow("Missing rig mask");
 });
 test("propagates cancellation to asset requests",async()=>{
  const controller=new AbortController();controller.abort();
  const fetcher=vi.fn(async(_url,options)=>{expect(options.signal).toBe(controller.signal);throw new DOMException("Aborted","AbortError");});vi.stubGlobal("fetch",fetcher);
  await expect(loadRig2dMeshes(root,root+"model/rig.json",controller.signal)).rejects.toThrow("Aborted");
 });
});

 test("colour detail validates its rectangle and version before renderer loading",async()=>{
  const bytes=new Uint8Array([1,2,3]);
  const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),v=>v.toString(16).padStart(2,"0")).join("");
  const detailed={...mesh(),colourDetail:{texture:"../textures/detail.png",sourceRectangle:[0,0,1,1],sha256:hash,baseSha256:hash}};
  const fetcher=vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith("rig.json")?{canvas:[512,1086],meshes:[{id:"face",path:"meshes/face.json"}]}:detailed,arrayBuffer:async()=>bytes.buffer}));
  vi.stubGlobal("fetch",fetcher);
  const loaded=await loadRig2dMeshes(root,root+"model/rig.json");
  expect(loaded.meshes[0].detailTextureUrl).toBe(root+"model/textures/detail.png");
  detailed.colourDetail.sha256="0".repeat(64);
  await expect(loadRig2dMeshes(root,root+"model/rig.json")).rejects.toThrow("version mismatch");
  detailed.colourDetail.sourceRectangle=[0,0,900,1];
  await expect(loadRig2dMeshes(root,root+"model/rig.json")).rejects.toThrow("outside canvas");
  expect(()=>validateRig2dMesh({...detailed,colourDetail:{...detailed.colourDetail,sourceRectangle:[2,0,1,1]}})).toThrow("Invalid rig colour detail");
 });
