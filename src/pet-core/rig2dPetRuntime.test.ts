import {afterEach,expect,test,vi} from 'vitest';
const mocks=vi.hoisted(()=>({create:vi.fn(),load:vi.fn()}));
vi.mock('./rig2dRenderer',()=>({Rig2dRenderer:{create:mocks.create}}));
vi.mock('./rig2dAssets',async importOriginal=>({...await importOriginal<typeof import('./rig2dAssets')>(),loadRig2dMeshes:mocks.load}));
import {Rig2dPetRuntime} from './rig2dPetRuntime';
import type {Renderer} from 'pixi.js';
const settings={meshPath:'model/meshes.json',modelPath:'model/runtime.json',actionsPath:'model/actions.json',displayHeight:170};
function setup(){
 vi.stubGlobal('window',{location:{href:'http://localhost/'}});
 const contract={schemaVersion:1,origin:[0,0,0],nodes:[{id:'root',parent:null,restOffset:[0,0,0],restPosition:[0,0,0]}],parameters:{},bindings:[],translation:[null,null,null],ik:[],materials:{},apertures:{}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('runtime.json')?contract:{idle:{duration:1,loop:true,keyframes:[{time:0,values:{}},{time:1,values:{}}]}}})));
 mocks.load.mockResolvedValue({canvas:[512,1086],meshes:[]});
 return {container:{pivot:{set:vi.fn()},scale:{set:vi.fn()}},update:vi.fn(),updateInto:vi.fn(),destroy:vi.fn()};
}
afterEach(()=>{vi.unstubAllGlobals();vi.clearAllMocks();});
test('cancellation during renderer creation destroys the late renderer',async()=>{
 const display=setup();let finish:(value:typeof display)=>void=()=>{};
 mocks.create.mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
 const controller=new AbortController(),pending=Rig2dPetRuntime.load({} as Renderer,'sample',settings,controller.signal);
 await vi.waitFor(()=>expect(mocks.create).toHaveBeenCalled());
 controller.abort();finish(display);await expect(pending).rejects.toThrow();expect(display.destroy).toHaveBeenCalledTimes(1);
});
test('owned renderer is disposed once and cannot play after destruction',async()=>{
 const display=setup();mocks.create.mockResolvedValue(display);
 const runtime=await Rig2dPetRuntime.load({} as Renderer,'sample',settings,new AbortController().signal);
 expect(runtime.play('idle')).toBe(true);expect(runtime.play('missing')).toBe(false);
 expect(runtime.hasAction('idle')).toBe(true);expect(runtime.hasAction('toString')).toBe(false);
 expect(()=>runtime.validateActionCatalog({idle:{loop:true}})).not.toThrow();
 expect(()=>runtime.validateActionCatalog({idle:{loop:false}})).toThrow('mismatch');
 expect(()=>runtime.validateActionCatalog({missing:{loop:true}})).toThrow('mismatch');
 runtime.destroy();runtime.destroy();expect(display.destroy).toHaveBeenCalledTimes(1);expect(runtime.play('idle')).toBe(false);
 expect(runtime.hasAction('idle')).toBe(false);
});

test('idle clock survives action changes and care action owns eye closure',async()=>{
 const {Rig2dModel}=await import('./rig2dModel');
 const display=setup();mocks.create.mockResolvedValue(display);
 const contract={schemaVersion:1,origin:[0,0,0],nodes:[{id:'root',parent:null,restOffset:[0,0,0],restPosition:[0,0,0]}],parameters:{gaze:{min:-1,max:1,initial:0,frequency:16},eye:{min:0,max:1,initial:1,frequency:60},breath:{min:-1,max:1,initial:0,frequency:12}},bindings:[],translation:[null,null,null],ik:[],materials:{},apertures:{},idle:{action:'idle',seed:1939,gaze:{first:.1,interval:[3,6],range:[1,1],followDelay:.12},blink:{first:10,interval:[3,6],duration:.16,doubleChance:0,doubleDelay:.4,doubleDuration:.14},channels:{gaze:{source:'gazeX',gain:1},eye:{source:'blink',gain:1},breath:{source:'wave',base:0,waves:[{amplitude:1,frequency:1,phase:0}]}}}};
 const actions={idle:{duration:1,loop:true,keyframes:[{time:0,values:{}},{time:1,values:{}}]},care:{duration:1,loop:false,keyframes:[{time:0,values:{eye:0}},{time:1,values:{eye:0}}]}};
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>({ok:true,json:async()=>url.endsWith('runtime.json')?contract:actions})));
 const targets=vi.spyOn(Rig2dModel.prototype,'setTargets');
 try {
  const runtime=await Rig2dPetRuntime.load({} as Renderer,'sample',settings,new AbortController().signal);
  runtime.play('idle');runtime.step(.3);expect(targets.mock.lastCall?.[0].breath).toBeCloseTo(Math.sin(.3));
  const gaze=targets.mock.lastCall?.[0].gaze;expect(gaze).not.toBe(0);
  runtime.play('care');runtime.step(.4);expect(targets.mock.lastCall?.[0].eye).toBe(0);
  expect(targets.mock.lastCall?.[0].gaze).toBe(gaze);expect(targets.mock.lastCall?.[0].breath).toBeCloseTo(Math.sin(.7));
  runtime.play('idle');runtime.step(.2);expect(targets.mock.lastCall?.[0].breath).toBeCloseTo(Math.sin(.9));expect(targets.mock.lastCall?.[0].eye).toBe(1);
  runtime.destroy();
 } finally {targets.mockRestore();}
});
