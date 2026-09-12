export type Rig2dAction = {duration:number;loop:boolean;keyframes:{time:number;values:Record<string,number>}[]};

/** Stateless target sampling shared by the pet and the action review workbench. */
export function sampleRig2dAction(action:Rig2dAction,seconds:number,definitions:Record<string,{initial:number}>,ambient:Record<string,number>={}):Record<string,number>{
 if(!Number.isFinite(seconds)||seconds<0)throw new Error('Invalid action elapsed time');
 const t=action.loop?seconds%action.duration:Math.min(seconds,action.duration);
 let left=action.keyframes[0],right=action.keyframes[action.keyframes.length-1];
 for(let i=1;i<action.keyframes.length;i++)if(action.keyframes[i].time>=t){left=action.keyframes[i-1];right=action.keyframes[i];break;}
 const u=Math.max(0,Math.min(1,(t-left.time)/(right.time-left.time))),blend=u*u*(3-2*u);
 const owned=new Set(action.keyframes.flatMap(key=>Object.keys(key.values)));
 return Object.fromEntries(Object.entries(definitions).map(([id,d])=>{
  // A closure-only action must not reset gaze, breathing, or other idle
  // channels. Explicit action channels retain their existing return-to-rest.
  if(!owned.has(id))return [id,ambient[id]??d.initial];
  const a=left.values[id]??d.initial,b=right.values[id]??d.initial;
  return [id,a+(b-a)*blend];
 }));
}
