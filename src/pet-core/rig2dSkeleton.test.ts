import {expect,test} from "vitest";
import {Rig2dSkeleton} from "./rig2dSkeleton";
const nodes=[{id:"tip",parent:"hinge",restOffset:[0,4,0]},{id:"root",parent:null,restOffset:[2,3,0]},{id:"hinge",parent:"root",restOffset:[0,5,0]}];
test("unordered arbitrary joint names resolve and preserve parent pivots",()=>{
 const rig=new Rig2dSkeleton(nodes,[{joint:"hinge",parameter:"bend",axis:"z"}]);
 const pose=rig.evaluate({bend:90});expect(pose.positions.hinge).toEqual([2,8,0]);expect(pose.positions.tip[0]).toBeCloseTo(-2);expect(pose.positions.tip[1]).toBeCloseTo(8);
});
test("parent rotation reaches descendants without changing segment lengths",()=>{
 const rig=new Rig2dSkeleton(nodes,[{joint:"root",parameter:"turn",axis:"y"},{joint:"hinge",parameter:"bend",axis:"z"}]);
 for(let i=0;i<=40;i++){const u=Math.sin(i*Math.PI/20),p=rig.evaluate({turn:u*30,bend:u*70},[7,0,2]);
  expect(Math.hypot(...p.positions.tip.map((v,j)=>v-p.positions.hinge[j]))).toBeCloseTo(4,12);
  expect(Math.hypot(...p.positions.hinge.map((v,j)=>v-p.positions.root[j]))).toBeCloseTo(5,12);
 }
});
test("invalid ancestry fails before evaluation",()=>{
 expect(()=>new Rig2dSkeleton([{id:"a",parent:"a",restOffset:[0,0,0]}],[])).toThrow("cycle");
 expect(()=>new Rig2dSkeleton([{id:"a",parent:"gone",restOffset:[0,0,0]}],[])).toThrow("parent");
});
test("constructor freezes supplied offsets and requires bound inputs",()=>{
 const input=[{id:"root",parent:null,restOffset:[1,2,3]}];const rig=new Rig2dSkeleton(input,[{joint:"root",parameter:"angle",axis:"x"}]);input[0].restOffset[0]=999;
 expect(rig.evaluate({angle:0}).positions.root).toEqual([1,2,3]);expect(()=>rig.evaluate({})).toThrow("parameter");
});
