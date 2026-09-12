export type Rig2dJoint = { id: string; parent: string | null; restOffset: number[] };
export type Rig2dRotationBinding = { joint: string; parameter: string; axis: "x" | "y" | "z"; gain?: number };
export type Rig2dPose = { positions: Record<string, number[]>; rotations: Record<string, number[][]> };
const identity=(): number[][] => [[1,0,0],[0,1,0],[0,0,1]];
const multiply=(a:number[][],b:number[][]):number[][] => a.map(row=>b[0].map((_,j)=>row.reduce((sum,v,k)=>sum+v*b[k][j],0)));
const transform=(a:number[][],v:number[]):number[] => a.map(row=>row.reduce((sum,x,i)=>sum+x*v[i],0));
function rotation(axis:"x"|"y"|"z",degrees:number):number[][] {
 const angle=degrees*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle);
 return axis==="x"?[[1,0,0],[0,c,-s],[0,s,c]]:axis==="y"?[[c,0,s],[0,1,0],[-s,0,c]]:[[c,-s,0],[s,c,0],[0,0,1]];
}
const vector=(v:number[])=>Array.isArray(v)&&v.length===3&&v.every(Number.isFinite);

/** Topological FK with ordered rotation bindings and immutable bone offsets. */
export class Rig2dSkeleton {
 private nodes:Rig2dJoint[]=[];
 private bindings:Rig2dRotationBinding[];
 constructor(nodes:Rig2dJoint[],bindings:Rig2dRotationBinding[]){
  const index=new Map(nodes.map(n=>[n.id,n]));
  if(!nodes.length||index.size!==nodes.length)throw new Error("Invalid skeleton identities");
  const active=new Set<string>(),done=new Set<string>();
  const visit=(node:Rig2dJoint):void=>{
   if(done.has(node.id))return;if(active.has(node.id))throw new Error("Skeleton cycle");
   if(typeof node.id!=="string"||!node.id||!vector(node.restOffset))throw new Error("Invalid skeleton joint");
   active.add(node.id);
   if(node.parent!==null){const parent=index.get(node.parent);if(!parent)throw new Error("Missing skeleton parent");visit(parent);}
   active.delete(node.id);done.add(node.id);this.nodes.push({...node,restOffset:[...node.restOffset]});
  };
  nodes.forEach(visit);
  for(const b of bindings)if(!index.has(b.joint)||!b.parameter||!["x","y","z"].includes(b.axis)||!Number.isFinite(b.gain??1))throw new Error("Invalid skeleton binding");
  this.bindings=bindings.map(b=>({...b}));
 }
 evaluate(parameters:Record<string,number>,translation:number[]=[0,0,0]):Rig2dPose{
  if(!vector(translation))throw new Error("Invalid root translation");
  const local:Record<string,number[][]>=Object.create(null),positions:Record<string,number[]>=Object.create(null),rotations:Record<string,number[][]>=Object.create(null);
  for(const b of this.bindings){const value=parameters[b.parameter];if(!Number.isFinite(value))throw new Error("Missing rotation parameter: "+b.parameter);local[b.joint]=multiply(local[b.joint]??identity(),rotation(b.axis,value*(b.gain??1)));}
  for(const n of this.nodes){
   const parentRotation=n.parent===null?identity():rotations[n.parent];
   rotations[n.id]=multiply(parentRotation,local[n.id]??identity());
   const offset=transform(parentRotation,n.restOffset),parentPosition=n.parent===null?translation:positions[n.parent];
   positions[n.id]=offset.map((v,i)=>v+parentPosition[i]);
  }
  return {positions,rotations};
 }
}
