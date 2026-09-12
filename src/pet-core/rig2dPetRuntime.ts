import { Rig2dIdle } from './rig2dIdle';
import { Rig2dDrag } from './rig2dDrag';
import type { Renderer } from 'pixi.js';
import { getPetBasePath, isSafePetRelativePath } from './petAssets';
import type { PetManifest } from './petAssets';
import { loadRig2dMeshes, resolveRig2dAssetUrl } from './rig2dAssets';
import { Rig2dRenderer } from './rig2dRenderer';
import { Rig2dModel } from './rig2dModel';
import type { Rig2dModelContract } from './rig2dModel';
import { Rig2dSecondary } from './rig2dSecondary';
import { sampleRig2dAction } from './rig2dActions';
import type { Rig2dAction as Action } from './rig2dActions';
export class Rig2dPetRuntime {
 readonly container;
 private current:string|null=null;
 private time=0;
 private destroyed=false;
 private secondary:Rig2dSecondary|null=null;
 private idle:Rig2dIdle|null=null;
 private drag:Rig2dDrag|null=null;
 private constructor(private model:Rig2dModel,private display:Rig2dRenderer,private actions:Record<string,Action>,readonly displaySize:{width:number;height:number}){this.container=display.container;}
 static async load(renderer:Renderer,petId:string,settings:NonNullable<PetManifest['rig2d']>,signal:AbortSignal):Promise<Rig2dPetRuntime>{
  if(![settings.meshPath,settings.modelPath,settings.actionsPath].every(isSafePetRelativePath)||!Number.isFinite(settings.displayHeight)||settings.displayHeight<=0)throw new Error('Invalid rig manifest');
  const root=new URL(getPetBasePath(petId)+'/',window.location.href).href;
  const path=(p:string)=>resolveRig2dAssetUrl(root,root,p);
  const read=async(p:string)=>{const r=await fetch(path(p),{signal});if(!r.ok)throw new Error('Rig configuration load failed');return r.json();};
  const [meshes,contract,actions]=await Promise.all([loadRig2dMeshes(root,path(settings.meshPath),signal),read(settings.modelPath) as Promise<Rig2dModelContract>,read(settings.actionsPath) as Promise<Record<string,Action>>]);
  signal.throwIfAborted();const model=new Rig2dModel(contract);
  for(const action of Object.values(actions)){
   if(!Number.isFinite(action.duration)||action.duration<=0||!Array.isArray(action.keyframes)||action.keyframes.length<2)throw new Error('Invalid rig action');
   let last=-1;for(const key of action.keyframes){if(!Number.isFinite(key.time)||key.time<0||key.time>action.duration||key.time<=last)throw new Error('Invalid rig action timing');last=key.time;model.pose(key.values);}
  }
  const secondary=contract.secondary?new Rig2dSecondary(contract.secondary):null;
  secondary?.step(0,model.values());
  const idle=contract.idle?new Rig2dIdle(contract.idle):null;
  const drag=contract.dragPhysics?new Rig2dDrag(contract.dragPhysics):null;
  if(drag){
   for(const id of [...Object.keys(drag.contract.channels),...Object.keys(drag.contract.held??{})])if(!model.definitions[id])throw new Error('Missing drag parameter '+id);
   model.pose(drag.contract.held??{});
  }
  if(idle){if(!Object.prototype.hasOwnProperty.call(actions,idle.contract.action))throw new Error('Missing idle action');model.pose(idle.step(0));}
  const display=await Rig2dRenderer.create(renderer,meshes.canvas,meshes.meshes);
  if(signal.aborted){display.destroy();signal.throwIfAborted();}
  const runtime=new Rig2dPetRuntime(model,display,actions,{width:settings.displayHeight*meshes.canvas[0]/meshes.canvas[1],height:settings.displayHeight});
  runtime.secondary=secondary;runtime.idle=idle;
  runtime.drag=drag;
  runtime.container.pivot.set(meshes.canvas[0]/2,meshes.canvas[1]);runtime.container.scale.set(settings.displayHeight/meshes.canvas[1]);
  try {runtime.step(0);return runtime;} catch(error){runtime.destroy();throw error;}
 }
 get detailMaterialCount():number{return this.display.detailMaterialCount;}
 get dragResponse():number{return this.drag?.lateral??0;}
 hasAction(name:string):boolean{return !this.destroyed&&Object.prototype.hasOwnProperty.call(this.actions,name);}
 validateActionCatalog(catalog:Record<string,{loop:boolean}>):void{
  for(const [name,spec] of Object.entries(catalog))if(!this.hasAction(name)||this.actions[name].loop!==spec.loop)throw new Error('Rig action catalog mismatch: '+name);
 }
 play(name:string):boolean{if(!this.hasAction(name))return false;this.current=name;this.time=0;return true;}
 beginDrag(x:number,y:number):void{this.drag?.begin(x,y);}
 moveDrag(x:number,y:number):void{this.drag?.move(x,y,this.displaySize.height);}
 endDrag():void{this.drag?.end();}
 step(seconds:number):void{
  if(this.destroyed)return;
  if(!Number.isFinite(seconds)||seconds<0)throw new Error('Invalid runtime elapsed time');
  const idleTargets=this.idle?.step(seconds);
  const dragTargets=this.drag?.step(seconds)??{};
  if(this.current){const action=this.actions[this.current];this.time+=seconds;
   const physicalDrag=this.current===this.drag?.contract.action;
   const targets=physicalDrag?{...Object.fromEntries(Object.entries(this.model.definitions).map(([id,d])=>[id,d.initial])),...idleTargets}:sampleRig2dAction(action,this.time,this.model.definitions,idleTargets);
   if(this.current===this.idle?.contract.action)Object.assign(targets,idleTargets);
   if(physicalDrag)Object.assign(targets,this.drag?.contract.held);
   for(const [id,value] of Object.entries(dragTargets))targets[id]=(targets[id]??this.model.definitions[id].initial)+value;
   this.model.setTargets(targets);
  }
  const pose=this.model.step(seconds);
  if(this.secondary)pose.secondary=this.secondary.step(seconds,pose.parameters,this.drag?.lateral??0);
  this.display.updateInto((mesh,target)=>this.model.deformInto(mesh,pose,target),id=>this.model.maskEnabled(id,pose));
 }
 destroy():void{if(this.destroyed)return;this.destroyed=true;this.display.destroy();}
}
