export type Rig2dIdleContract={
 action:string;seed:number;gaze:{first:number;interval:[number,number];range:[number,number];followDelay:number};
 blink:{first:number;interval:[number,number];duration:number;doubleChance:number;doubleDelay:number;doubleDuration:number};
 channels:Record<string,{source:'gazeX'|'gazeY'|'headX'|'headY'|'blink';gain:number}|{source:'wave';base:number;waves:{amplitude:number;frequency:number;phase:number}[]}>;
};
/** The director clock is independent of action time and parameter interpolation. */
export class Rig2dIdle {
 readonly contract:Rig2dIdleContract;
 time=0;private seed:number;private nextGaze:number;private nextBlink:number;
 private blinkEnd=-1;private doubleAt=Infinity;private followAt=Infinity;
 private gaze=[0,0];private head=[0,0];
 constructor(contract:Rig2dIdleContract){
  this.contract=structuredClone(contract);const {gaze:g,blink:b}=this.contract;
  if(!contract.action||!Number.isInteger(contract.seed)||contract.seed<=0||contract.seed>0xffffffff||
   ![g.first,...g.interval,...g.range,g.followDelay,b.first,...b.interval,b.duration,b.doubleChance,b.doubleDelay,b.doubleDuration].every(v=>Number.isFinite(v)&&v>=0)||
   g.interval[0]<=0||b.interval[0]<=0||g.interval[1]<g.interval[0]||b.interval[1]<b.interval[0]||b.doubleChance>1)throw Error('Invalid idle configuration');
  for(const c of Object.values(contract.channels)){
   if(c.source==='wave'){if(!Number.isFinite(c.base)||!Array.isArray(c.waves)||c.waves.some(w=>![w.amplitude,w.frequency,w.phase].every(Number.isFinite)))throw Error('Invalid idle wave');}
   else if(!['gazeX','gazeY','headX','headY','blink'].includes(c.source)||!Number.isFinite(c.gain))throw Error('Invalid idle channel');
  }
  this.seed=contract.seed;this.nextGaze=g.first;this.nextBlink=b.first;
 }
 private random():number{let x=this.seed;x^=x<<13;x^=x>>>17;x^=x<<5;this.seed=x>>>0;return this.seed/4294967296;}
 step(dt:number):Record<string,number>{
  if(!Number.isFinite(dt)||dt<0)throw Error('Invalid idle elapsed time');this.time+=dt;
  const t=this.time,{gaze:g,blink:b}=this.contract;
  if(t>=this.nextGaze){this.gaze=g.range.map(r=>(this.random()-.5)*r);this.followAt=t+g.followDelay;this.nextGaze=t+g.interval[0]+this.random()*(g.interval[1]-g.interval[0]);}
  if(t>=this.followAt){this.head=[...this.gaze];this.followAt=Infinity;}
  if(t>=this.nextBlink){this.blinkEnd=t+b.duration;this.nextBlink=t+b.interval[0]+this.random()*(b.interval[1]-b.interval[0]);if(this.random()<b.doubleChance)this.doubleAt=t+b.doubleDelay;}
  if(t>=this.doubleAt){this.blinkEnd=t+b.doubleDuration;this.doubleAt=Infinity;}
  const values={gazeX:this.gaze[0],gazeY:this.gaze[1],headX:this.head[0],headY:this.head[1],blink:t<this.blinkEnd?0:1};
  return Object.fromEntries(Object.entries(this.contract.channels).map(([id,c])=>[id,c.source==='wave'?c.base+c.waves.reduce((sum,w)=>sum+w.amplitude*Math.sin(t*w.frequency+w.phase),0):values[c.source]*c.gain]));
 }
}
