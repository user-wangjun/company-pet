import {Rig2dParameters} from './rig2dParameters.ts';
import type {Rig2dParameterDefinitions} from './rig2dParameters.ts';
import {Rig2dSkeleton} from './rig2dSkeleton.ts';
import type {Rig2dJoint,Rig2dRotationBinding,Rig2dPose} from './rig2dSkeleton.ts';
import {solveRig2dTwoBone} from './rig2dIk.ts';
import {deformRig2dEye,deformRig2dBreath,rig2dDepthCap,rig2dFaceSurfaceDepth} from './rig2dDeformation.ts';
import type {Rig2dEyeShape,Rig2dFaceSurface} from './rig2dDeformation.ts';
import type {Rig2dMeshData} from './rig2dAssets.ts';
import type {Rig2dIdleContract} from './rig2dIdle.ts';
import type {Rig2dSecondaryContract} from './rig2dSecondary.ts';
import type {Rig2dDragContract} from './rig2dDrag.ts';
type Joint=Rig2dJoint & {restPosition:number[]};
type Eye=Rig2dEyeShape & {kind:'eye';open:string;gaze:string[]};
type Breath={kind:'breath';parameter:string;centre:number[];radiusY:number;radialGain:number};
type Material={joints:string[];weights?:number[][];local?:Eye|Breath;depth?:{centre:number[];radii:number[];hemisphere:number;faceSurface?:Rig2dFaceSurface}};
export type Rig2dModelContract={
 schemaVersion:1;origin:number[];nodes:Joint[];parameters:Rig2dParameterDefinitions;bindings:Rig2dRotationBinding[];
 translation:(string|null)[];ik:{upper:string;middle:string;end:string;pole:number[];descendants:string[];release?:string}[];
 materials:Record<string,Material>;apertures:Record<string,{parameter:string;threshold:number}>;
 secondary?:Rig2dSecondaryContract;idle?:Rig2dIdleContract;dragPhysics?:Rig2dDragContract;
 grounding?:{maxDrop:number;reachMargin:number};
};
export type Rig2dModelPose=Rig2dPose & {parameters:Record<string,number>;groundingDrop?:number;secondary?:Record<string,{dx:number;rootY:number;tipY:number}>};
export type Rig2dContactTargets=Readonly<Record<string,readonly number[]>>;
const add=(a:number[],b:number[])=>a.map((v,i)=>v+b[i]);
const mv=(a:number[][],v:number[])=>a.map(row=>row.reduce((s,x,i)=>s+x*v[i],0));
const identity=()=>[[1,0,0],[0,1,0],[0,0,1]];

/** JSON-driven pose and material evaluation. No pet names or asset paths. */
export class Rig2dModel{
 readonly parameters:Rig2dParameters;
 readonly definitions:Rig2dParameterDefinitions;
 private contract:Rig2dModelContract;
 private forward:Rig2dSkeleton;
 private nodes:Record<string,Joint>;
 private depthSamples=new WeakMap<Rig2dMeshData,Float64Array>();
 constructor(contract:Rig2dModelContract){
  this.contract=structuredClone(contract);this.parameters=new Rig2dParameters(contract.parameters);this.definitions=this.parameters.definitions;
  this.forward=new Rig2dSkeleton(contract.nodes,contract.bindings);this.nodes=Object.fromEntries(this.contract.nodes.map(n=>[n.id,n]));
  if(contract.schemaVersion!==1||contract.origin.length!==3||!contract.origin.every(Number.isFinite)||contract.translation.length!==3)throw new Error('Invalid model coordinates');
  const parameter=(id:string)=>{if(!Object.prototype.hasOwnProperty.call(this.definitions,id))throw new Error('Missing model parameter: '+id);};
  const joint=(id:string)=>{if(!Object.prototype.hasOwnProperty.call(this.nodes,id))throw new Error('Missing model joint: '+id);};
  contract.translation.forEach(id=>{if(id!==null)parameter(id);});contract.bindings.forEach(b=>parameter(b.parameter));
  for(const chain of contract.ik){
   [chain.upper,chain.middle,chain.end,...chain.descendants].forEach(joint);
   if(this.nodes[chain.middle].parent!==chain.upper||this.nodes[chain.end].parent!==chain.middle)throw new Error('Invalid IK chain');
   if(chain.release!==undefined){parameter(chain.release);const d=this.definitions[chain.release];if(d.min!==0||d.max!==1||d.initial!==0)throw new Error('Invalid contact release parameter');}
  }
  for(const material of Object.values(contract.materials)){
   if(!material.joints.length)throw new Error('Missing skin joints');material.joints.forEach(joint);
   if(material.joints.length>1&&!material.weights)throw new Error('Missing skin weights');
   for(const weights of material.weights??[])if(weights.length!==material.joints.length||weights.some(w=>!Number.isFinite(w)||w<0)||Math.abs(weights.reduce((a,b)=>a+b,0)-1)>1e-8)throw new Error('Invalid skin weights');
   if(material.local?.kind==='eye'){parameter(material.local.open);material.local.gaze.forEach(parameter);}
   if(material.local?.kind==='breath')parameter(material.local.parameter);
   const surface=material.depth?.faceSurface;
   if(surface){
    if(!Number.isFinite(surface.centreX)||surface.blendY.length!==2||!surface.blendY.every(Number.isFinite)||surface.blendY[0]>=surface.blendY[1]||surface.sections.length<2)throw new Error('Invalid face surface');
    for(let i=0;i<surface.sections.length;i++){const s=surface.sections[i];if(![s.y,s.halfWidth,s.centreDepth,s.edgeDepth].every(Number.isFinite)||s.halfWidth<=0||(i>0&&s.y<=surface.sections[i-1].y))throw new Error('Invalid face surface section');}
   }
  }
  Object.values(contract.apertures).forEach(a=>parameter(a.parameter));
  if(contract.grounding&&(!Number.isFinite(contract.grounding.maxDrop)||contract.grounding.maxDrop<0||!Number.isFinite(contract.grounding.reachMargin)||contract.grounding.reachMargin<=0))throw new Error('Invalid grounding limits');
 }
 setTargets(targets:Record<string,number>):void{this.parameters.setTargets(targets);}
 values():Record<string,number>{return this.parameters.values();}
 step(seconds:number,contacts?:Rig2dContactTargets):Rig2dModelPose{this.parameters.step(seconds);return this.pose(this.values(),contacts);}
 pose(values:Record<string,number>=this.values(),contacts?:Rig2dContactTargets):Rig2dModelPose{
  if(contacts!==undefined)for(const [id,target] of Object.entries(contacts)){
   if(!this.contract.ik.some(chain=>chain.end===id)||!Array.isArray(target)||target.length!==3||!target.every(Number.isFinite))throw new Error('Invalid external contact: '+id);
  }
  const p={...Object.fromEntries(Object.entries(this.definitions).map(([id,d])=>[id,d.initial])),...values};
  for(const [id,v] of Object.entries(p)){const d=this.definitions[id];if(!d||!Number.isFinite(v)||v<d.min||v>d.max)throw new Error('Invalid model pose');if(Object.is(v,-0))p[id]=0;}
  const translation=this.contract.translation.map(id=>id===null?0:p[id]);let pose=this.forward.evaluate(p,translation),groundingDrop=0;
  if(this.contract.grounding){
   const limits=this.contract.grounding;
   for(const chain of this.contract.ik){
    // Keep stance reach available throughout release and return; dropping a
    // constraint exactly at release=1 would make the pelvis jump at that edge.
    const target=contacts!==undefined?contacts[chain.end]:this.nodes[chain.end].restPosition;
    if(target===undefined)continue;
    const root=pose.positions[chain.upper],dx=target[0]-root[0],dy=target[1]-root[1],dz=target[2]-root[2];
    const reach=Math.hypot(...this.nodes[chain.middle].restOffset)+Math.hypot(...this.nodes[chain.end].restOffset)-limits.reachMargin;
    if(reach<=0||dx*dx+dz*dz>=reach*reach)throw new Error('Ground contact horizontally unreachable');
    groundingDrop=Math.max(groundingDrop,dy-Math.sqrt(reach*reach-dx*dx-dz*dz));
   }
   if(groundingDrop>limits.maxDrop)throw new Error('Grounding correction exceeds limit');
   if(groundingDrop>0){translation[1]+=groundingDrop;pose=this.forward.evaluate(p,translation);}
  }
  for(const chain of this.contract.ik){
   // An omitted set retains desktop floor locking. An explicit empty set
   // releases it, so a room gait can lift a foot without changing the model.
   let target:readonly number[]|undefined;
   if(contacts!==undefined)target=contacts[chain.end];
   else if(chain.release!==undefined){
    const rest=this.nodes[chain.end].restPosition,forward=pose.positions[chain.end],release=p[chain.release];
    // Blend reachable endpoint targets, never joint positions or bone lengths.
    // The planted foot remains fixed until its release channel is raised.
    target=rest.map((v,i)=>v+(forward[i]-v)*release);
    if(translation.every(v=>v===0)&&forward.every((v,i)=>v===rest[i]))continue;
   }else target=translation.some(v=>v!==0)?this.nodes[chain.end].restPosition:undefined;
   if(target===undefined)continue;
   const solved=solveRig2dTwoBone(pose.positions[chain.upper],[...target],this.nodes[chain.middle].restOffset,this.nodes[chain.end].restOffset,chain.pole);
   pose.positions[chain.middle]=solved.middle;pose.positions[chain.end]=solved.end;
   pose.rotations[chain.upper]=solved.upperRotation;pose.rotations[chain.middle]=solved.lowerRotation;pose.rotations[chain.end]=identity();
   for(const id of chain.descendants){const n=this.nodes[id];if(n.parent===null)throw new Error('Invalid IK descendant');pose.positions[id]=add(pose.positions[n.parent],mv(pose.rotations[n.parent],n.restOffset));pose.rotations[id]=identity();}
  }
  return {...pose,parameters:p,...(this.contract.grounding?{groundingDrop}:{})};
 }
 /** Local offsets follow the posed joint in native model coordinates. */
 anchorPosition(nodeId:string|undefined,local:readonly number[],pose:Rig2dModelPose):number[]{
  if(local.length!==3||!local.every(Number.isFinite))throw new Error('Invalid anchor offset');
  if(nodeId===undefined)return [...local];
  if(!Object.prototype.hasOwnProperty.call(this.nodes,nodeId)||!Object.prototype.hasOwnProperty.call(pose.positions,nodeId))throw new Error('Missing anchor joint: '+nodeId);
  return add(pose.positions[nodeId],mv(pose.rotations[nodeId],[...local]));
 }
 maskEnabled(id:string,pose:Rig2dModelPose):boolean{const a=this.contract.apertures[id];return !a||pose.parameters[a.parameter]>a.threshold;}
 deform(mesh:Rig2dMeshData,pose:Rig2dModelPose,depthYScale=0):number[][]{
  const result:number[][]=new Array(mesh.positions.length);
  this.deformVertices(mesh,pose,depthYScale,(i,x,y)=>{result[i]=[x,y];});
  return result;
 }
 /** Write into reusable staging storage; do not allocate a pair per vertex. */
 deformInto(mesh:Rig2dMeshData,pose:Rig2dModelPose,target:Float32Array,depthYScale=0):void{
  if(!(target instanceof Float32Array)||target.length!==mesh.positions.length*2)throw new Error('Invalid deformation buffer');
  this.deformVertices(mesh,pose,depthYScale,(i,x,y)=>{target[i*2]=x;target[i*2+1]=y;});
 }
 private deformVertices(mesh:Rig2dMeshData,pose:Rig2dModelPose,depthYScale:number,write:(index:number,x:number,y:number)=>void):void{
  if(!Number.isFinite(depthYScale))throw new Error('Invalid depth projection');
  const material=this.contract.materials[mesh.id];if(!material)throw new Error('Missing material controller');
  if(material.weights&&material.weights.length!==mesh.positions.length)throw new Error('Skin weight count mismatch');
  const origin=this.contract.origin;
  // Joint transforms and channel lookups are constant across this material.
  // Keep all vertex coordinates and weights; avoid allocating intermediate
  // vectors and computing the unused projected Z component for each joint.
  const joints=material.joints.map(id=>({rest:this.nodes[id].restPosition,position:pose.positions[id],rotation:pose.rotations[id]}));
  const local=material.local,lag=pose.secondary?.[mesh.id];
  const gaze=local?.kind==='eye'?local.gaze.map(id=>pose.parameters[id]):[];
  let samples=material.depth?this.depthSamples.get(mesh):undefined;
  if(material.depth&&(!samples||samples.length!==mesh.positions.length*3)){
   samples=new Float64Array(mesh.positions.length*3);samples.fill(NaN);this.depthSamples.set(mesh,samples);
  }
  const last=joints.length-1;
  for(let index=0;index<mesh.positions.length;index++){
   let [x,y]=mesh.positions[index];
   if(local?.kind==='eye')[x,y]=deformRig2dEye(x,y,local,pose.parameters[local.open],gaze);
   if(local?.kind==='breath')[x,y]=deformRig2dBreath(x,y,local,pose.parameters[local.parameter]);
   if(lag&&y>lag.rootY){const t=Math.max(0,Math.min(1,(y-lag.rootY)/(lag.tipY-lag.rootY)));x+=lag.dx*t*t*(3-2*t);}
   let depth:number|null=null;
   if(material.depth&&samples){
    const slot=index*3;
    // Depth is a source-space field. Joint rotation does not change it.
    // Exact x/y keys also invalidate moving eye, breath and hair samples.
    if(samples[slot]===x&&samples[slot+1]===y)depth=samples[slot+2];
    else{
     depth=rig2dDepthCap(x,y,material.depth.centre,material.depth.radii,material.depth.hemisphere);
     if(material.depth.faceSurface)depth=rig2dFaceSurfaceDepth(x,y,depth,material.depth.faceSurface);
     samples[slot]=x;samples[slot+1]=y;samples[slot+2]=depth;
    }
   }
   const base=joints[last],bx=x-origin[0]-base.rest[0],by=y-origin[1]-base.rest[1],bz=depth===null?0:depth-base.rest[2];
   const baseX=base.position[0]+base.rotation[0][0]*bx+base.rotation[0][1]*by+base.rotation[0][2]*bz;
   const baseY=base.position[1]+base.rotation[1][0]*bx+base.rotation[1][1]*by+base.rotation[1][2]*bz;
   let px=baseX,py=baseY;
   let pz=depthYScale===0?0:base.position[2]+base.rotation[2][0]*bx+base.rotation[2][1]*by+base.rotation[2][2]*bz;
   for(let j=0;j<last;j++){
    const joint=joints[j],dx=x-origin[0]-joint.rest[0],dy=y-origin[1]-joint.rest[1],dz=depth===null?0:depth-joint.rest[2],w=material.weights![index][j];
    const qx=joint.position[0]+joint.rotation[0][0]*dx+joint.rotation[0][1]*dy+joint.rotation[0][2]*dz;
    const qy=joint.position[1]+joint.rotation[1][0]*dx+joint.rotation[1][1]*dy+joint.rotation[1][2]*dz;
    px+=(qx-baseX)*w;py+=(qy-baseY)*w;
    if(depthYScale!==0){
     const qz=joint.position[2]+joint.rotation[2][0]*dx+joint.rotation[2][1]*dy+joint.rotation[2][2]*dz;
     const baseZ=base.position[2]+base.rotation[2][0]*bx+base.rotation[2][1]*by+base.rotation[2][2]*bz;
     pz+=(qz-baseZ)*w;
    }
   }
   write(index,px+origin[0],py+origin[1]+pz*depthYScale);
  }
 }
}
