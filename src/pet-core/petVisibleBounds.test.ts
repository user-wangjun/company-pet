import {resolvePetInteractionManifest} from './petInteractionManifest';
import {afterEach,expect,test,vi} from 'vitest';
import {measurePetVisibleBounds} from './petVisibleBounds';
import {createPetCatalog,type PetManifest} from './petAssets';
const candidate = {
 id:'sample-rig',displayName:'Sample',description:'Synthetic rig fixture',previewPath:'preview.png',
 rig2d:{meshPath:'model/meshes.json',modelPath:'model/runtime.json',actionsPath:'model/actions.json',displayHeight:170},
 actions:{idle:{loop:true},singleClick:{loop:false},doubleClick:{loop:false},drag:{loop:true},eyeCare:{loop:false},water:{loop:false},meal:{loop:false},sleep:{loop:false}},
 interactions:{idle:{animation:'idle'},singleClick:{animation:'singleClick',durationMs:2400},doubleClick:{animation:'doubleClick',durationMs:2400},
  drag:{directionMode:'rows' as const,right:'drag',left:'drag'},
  reminders:{eyeCare:{animation:'eyeCare',durationMs:2400},water:{animation:'water',durationMs:2400},meal:{animation:'meal',durationMs:2400},sleep:{animation:'sleep',durationMs:2400}}},
};
const manifest=candidate as Extract<PetManifest,{rig2d:unknown}>;
afterEach(()=>vi.unstubAllGlobals());
test('rig catalog uses a preview image without a spritesheet',()=>{
 expect(manifest).not.toHaveProperty('spritesheetPath');
 const [item]=createPetCatalog([manifest.id],{[manifest.id]:manifest},manifest.id);
 expect(item.previewKind).toBe('image');expect(item.previewUrl).toBe('/pets/'+manifest.id+'/'+manifest.previewPath);
});
test('rig window covers the complete scaled canvas without image/frame sampling',async()=>{
 const request=vi.fn(async()=>({ok:true,json:async()=>({canvas:[512,1086]})}));vi.stubGlobal('fetch',request);
 expect(await measurePetVisibleBounds(manifest)).toEqual({x:42,y:39,width:81,height:170});
 expect(request).toHaveBeenCalledTimes(1);
});
test('invalid rig paths fail before a request and invalid canvas bounds fail closed',async()=>{
 const request=vi.fn(async()=>({ok:true,json:async()=>({canvas:[512,0]})}));vi.stubGlobal('fetch',request);
 await expect(measurePetVisibleBounds({...manifest,rig2d:{...manifest.rig2d!,meshPath:'../outside.json'}})).rejects.toThrow('path');expect(request).not.toHaveBeenCalled();
 await expect(measurePetVisibleBounds(manifest)).rejects.toThrow('bounds');
});

 test('rig interaction catalog has no sprite frame metadata and validates action references',()=>{
  const resolved=resolvePetInteractionManifest(candidate);
  expect(candidate).not.toHaveProperty('animations');expect(resolved.animations).toEqual({});
  expect(resolved.idle.animation).toBe('idle');expect(resolved.reminders.eyeCare.animation).toBe('eyeCare');
  expect(()=>resolvePetInteractionManifest({...candidate,actions:{...candidate.actions,eyeCare:undefined}})).toThrow();
  expect(()=>resolvePetInteractionManifest({...candidate,interactions:{...candidate.interactions,drag:{...candidate.interactions.drag,takeoffFrame:0}}})).toThrow('Sprite frame option');
 });
