import {expect,test} from "vitest";
import {Rig2dParameters} from "./rig2dParameters";
const make=()=>new Rig2dParameters({angle:{min:-10,max:10,initial:0,frequency:12},open:{min:0,max:1,initial:1,frequency:60}});
test("action reversal retains position and velocity; invalid edit is atomic",()=>{
 const p=make();p.setTargets({angle:10});p.step(.1);const before={...p.state.angle};
 p.setTargets({angle:-10});expect(p.state.angle.value).toBe(before.value);expect(p.state.angle.velocity).toBe(before.velocity);
 expect(()=>p.setTargets({angle:4,unknown:1})).toThrow();expect(p.state.angle.target).toBe(-10);
});
test("continuous response is cadence invariant and settles exactly",()=>{
 const a=make(),b=make();a.setTargets({angle:8});b.setTargets({angle:8});a.step(1);for(let i=0;i<120;i++)b.step(1/120);
 expect(a.state.angle.value).toBeCloseTo(b.state.angle.value,12);expect(a.state.angle.velocity).toBeCloseTo(b.state.angle.velocity,12);
 a.setTargets({angle:0});a.step(10);expect(a.state.angle).toEqual({value:0,velocity:0,target:0});
});
test("ordered layers compose weighted override/add/multiply without resetting state",()=>{
 const p=make();p.step(.1);p.setLayers([{mode:"override",weight:.5,values:{angle:8}},{mode:"add",weight:.5,values:{angle:2}},{mode:"multiply",weight:.5,values:{angle:2}}]);
 expect(p.state.angle.target).toBe(7.5);expect(p.state.angle.value).toBe(0);
 expect(()=>p.setLayers([{mode:"add",weight:1,values:{angle:2}},{mode:"override",weight:NaN,values:{angle:1}}])).toThrow();expect(p.state.angle.target).toBe(7.5);
});
test("malformed definitions and nonfinite elapsed time fail before mutation",()=>{
 expect(()=>new Rig2dParameters({x:{min:0,max:1,initial:2,frequency:12}})).toThrow();
 const p=make();expect(()=>p.step(Infinity)).toThrow();expect(p.values()).toEqual({angle:0,open:1});
});
