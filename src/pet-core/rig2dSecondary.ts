type Group={driver:string;frequency:number;damping:number;lag:number;limit:number;speed:number;dragGain?:number};
export type Rig2dSecondaryContract={step:number;maxSubsteps:number;maxElapsed:number;groups:Record<string,Group>;materials:Record<string,{group:string;rootY:number;tipY:number}>};
const clamp=(x:number,a:number,b:number)=>Math.max(a,Math.min(b,x));
export class Rig2dSecondary{
 readonly contract:Rig2dSecondaryContract;
 readonly state:Record<string,{x:number;v:number}>;
 accumulator=0;discardedSeconds=0;
 private previous:Record<string,number>|null=null;
 constructor(contract:Rig2dSecondaryContract){
  if(!Number.isFinite(contract.step)||contract.step<=0||!Number.isInteger(contract.maxSubsteps)||contract.maxSubsteps<1||!Number.isFinite(contract.maxElapsed)||contract.maxElapsed<=0||contract.maxElapsed>contract.step*contract.maxSubsteps+1e-10)throw new Error('Invalid secondary timestep');
  for(const g of Object.values(contract.groups))if(!g.driver||![g.frequency,g.damping,g.lag,g.limit,g.speed].every(Number.isFinite)||g.frequency<=0||g.damping<=0||g.limit<0||g.speed<0||g.frequency*contract.step>.5)throw new Error('Invalid secondary group');
  for(const g of Object.values(contract.groups))if(g.dragGain!==undefined&&!Number.isFinite(g.dragGain))throw new Error('Invalid drag secondary gain');
  for(const m of Object.values(contract.materials))if(!Object.prototype.hasOwnProperty.call(contract.groups,m.group)||!Number.isFinite(m.rootY)||!Number.isFinite(m.tipY)||m.tipY<=m.rootY)throw new Error('Invalid secondary attachment');
  this.contract=structuredClone(contract);this.state=Object.fromEntries(Object.keys(contract.groups).map(id=>[id,{x:0,v:0}]));
 }
 step(seconds:number,parameters:Record<string,number>,dragForce=0):Record<string,{dx:number;rootY:number;tipY:number}>{
  if(!Number.isFinite(seconds)||seconds<0||!Number.isFinite(dragForce))throw new Error('Invalid secondary elapsed time');
  for(const g of Object.values(this.contract.groups))if(!Number.isFinite(parameters[g.driver]))throw new Error('Missing secondary driver '+g.driver);
  if(seconds===0)return this.snapshot();
  const dt=Math.min(seconds,this.contract.maxElapsed);this.discardedSeconds+=seconds-dt;
  const previous=this.previous??parameters,targets:Record<string,number>={};
  for(const [id,g] of Object.entries(this.contract.groups))targets[id]=clamp(-(parameters[g.driver]-previous[g.driver])/seconds*g.lag+dragForce*(g.dragGain??0),-g.limit,g.limit);
  this.previous={...parameters};this.accumulator+=dt;let steps=0;
  while(this.accumulator+1e-12>=this.contract.step&&steps<this.contract.maxSubsteps){
   for(const [id,g] of Object.entries(this.contract.groups)){
    const s=this.state[id],h=this.contract.step;
    s.v=clamp(s.v+(g.frequency*g.frequency*(targets[id]-s.x)-2*g.damping*g.frequency*s.v)*h,-g.speed,g.speed);
    s.x=clamp(s.x+s.v*h,-g.limit,g.limit);
    if(Math.abs(s.x)===g.limit&&s.x*s.v>0)s.v=0;
    if(targets[id]===0&&Math.abs(s.x)<1e-8&&Math.abs(s.v)<1e-8){s.x=0;s.v=0;}
   }
   this.accumulator-=this.contract.step;steps++;
  }
  this.accumulator=Math.max(0,this.accumulator);return this.snapshot();
 }
 snapshot():Record<string,{dx:number;rootY:number;tipY:number}>{return Object.fromEntries(Object.entries(this.contract.materials).map(([id,m])=>[id,{dx:this.state[m.group].x,rootY:m.rootY,tipY:m.tipY}]));}
}
