import {expect,test} from "vitest";
import {solveRig2dTwoBone} from "./rig2dIk";
test("planted endpoint and original lengths survive a weight shift",()=>{
 const upper=[0,5,1],lower=[0,5,-1],target=[0,10,0];
 for(let i=0;i<=40;i++){const t=Math.sin(i*Math.PI/40),root=[t,.5*t,0],p=solveRig2dTwoBone(root,target,upper,lower,[0,0,1]);
  expect(p.end).toEqual(target);expect(p.middle[2]).toBeGreaterThan(0);
  expect(Math.hypot(...p.middle.map((v,j)=>v-root[j]))).toBeCloseTo(Math.hypot(...upper),12);
  expect(Math.hypot(...target.map((v,j)=>v-p.middle[j]))).toBeCloseTo(Math.hypot(...lower),12);
 }
});
test("pole chooses the branch and ambiguous or unreachable targets fail",()=>{
 expect(solveRig2dTwoBone([0,0,0],[0,8,0],[0,5,0],[0,5,0],[0,0,-1]).middle[2]).toBeLessThan(0);
 expect(()=>solveRig2dTwoBone([0,0,0],[0,11,0],[0,5,0],[0,5,0],[0,0,1])).toThrow("unreachable");
 expect(()=>solveRig2dTwoBone([0,0,0],[0,8,0],[0,5,0],[0,5,0],[0,1,0])).toThrow("Ambiguous");
});
