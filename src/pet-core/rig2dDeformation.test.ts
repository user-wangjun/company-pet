import {expect,test} from 'vitest';
import {rig2dFaceSurfaceDepth,type Rig2dFaceSurface} from './rig2dDeformation';

const profile:Rig2dFaceSurface={centreX:0,blendY:[-20,0],sections:[
 {y:0,halfWidth:48,centreDepth:60,edgeDepth:6},
 {y:20,halfWidth:43,centreDepth:67,edgeDepth:18},
 {y:50,halfWidth:4,centreDepth:45,edgeDepth:45},
]};

test('facial centre landmarks retain their authored depths and chin does not collapse into the skull plane',()=>{
 expect(rig2dFaceSurfaceDepth(0,20,5,profile)).toBe(67);
 expect(rig2dFaceSurfaceDepth(0,50,5,profile)).toBe(45);
 expect(rig2dFaceSurfaceDepth(4,50,5,profile)).toBe(45);
 expect(rig2dFaceSurfaceDepth(0,-20,13,profile)).toBe(13);
});

test('facial cross sections remain ordered when projected at both yaw limits',()=>{
 for(const y of [0,10,20,35,50])for(const sign of [-1,1]){
  const angle=sign*20*Math.PI/180;let previous=-Infinity;
  for(let x=-55;x<=55;x+=.1){
   const projected=x*Math.cos(angle)+rig2dFaceSurfaceDepth(x,y,5,profile)*Math.sin(angle);
   expect(projected).toBeGreaterThan(previous);previous=projected;
  }
 }
});

test('depth slope joins the flat outside surface without a cusp',()=>{
 const h=1e-4,edge=48;
 const left=(rig2dFaceSurfaceDepth(edge,0,5,profile)-rig2dFaceSurfaceDepth(edge-h,0,5,profile))/h;
 const right=(rig2dFaceSurfaceDepth(edge+h,0,5,profile)-rig2dFaceSurfaceDepth(edge,0,5,profile))/h;
 expect(Math.abs(left-right)).toBeLessThan(.0001);
});
