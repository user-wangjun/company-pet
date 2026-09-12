import { describe,expect,it } from 'vitest';
import { sampleRig2dAction } from './rig2dActions';
import type { Rig2dAction } from './rig2dActions';

describe('rig action target sampling',()=>{
 const definitions={elbow:{initial:0},eye:{initial:1}};
 const action:Rig2dAction={duration:2,loop:false,keyframes:[{time:0,values:{}},{time:1,values:{elbow:12,eye:0}},{time:2,values:{}}]};
 it('returns sparse channels to their defaults and holds the final pose',()=>{
  expect(sampleRig2dAction(action,1,definitions)).toEqual({elbow:12,eye:0});
  expect(sampleRig2dAction(action,1.5,definitions)).toEqual({elbow:6,eye:.5});
  expect(sampleRig2dAction(action,20,definitions)).toEqual({elbow:0,eye:1});
 });
 it('wraps looping time while allowing an explicit final-key review',()=>{
  const loop={...action,loop:true,keyframes:[{time:0,values:{elbow:0}},{time:2,values:{elbow:12}}]};
  expect(sampleRig2dAction(loop,2,definitions).elbow).toBe(0);
  expect(sampleRig2dAction({...loop,loop:false},2,definitions).elbow).toBe(12);
  expect(sampleRig2dAction(loop,3,definitions).elbow).toBe(6);
 });
});
