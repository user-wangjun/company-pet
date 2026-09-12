import {expect,test} from 'vitest';
import {Rig2dDrag} from './rig2dDrag';
const contract={action:'drag',frequency:9,damping:.65,velocityGain:.32,accelerationGain:.025,channels:{roll:{axis:'x' as const,gain:5},pitch:{axis:'y' as const,gain:4}}};
test('actual travel causes lag, reversal changes it, release settles without a snap',()=>{
 const drag=new Rig2dDrag(contract);drag.begin(0,0);
 for(let i=1;i<=60;i++){drag.move(i*3,0,170);drag.step(1/60);}
 expect(drag.step(0).roll).toBeLessThan(-1);
 for(let i=1;i<=60;i++){drag.move(180-i*6,0,170);drag.step(1/60);}
 expect(drag.step(0).roll).toBeGreaterThan(2);
 const before=drag.step(0);drag.end();expect(drag.step(0)).toEqual(before);
 for(let i=0;i<600;i++)drag.step(1/60);
 expect(drag.step(0)).toEqual({roll:0,pitch:0});
});
test('subdividing pointer events preserves frame input and huge/stalled motion is bounded',()=>{
 const a=new Rig2dDrag(contract),b=new Rig2dDrag(contract);a.begin(0,0);b.begin(0,0);
 for(let i=1;i<=60;i++){
  a.move(i*3,i,170);
  for(let j=1;j<=4;j++)b.move((i-1)*3+j*.75,i-1+j*.25,170);
  expect(a.step(1/60).roll).toBeCloseTo(b.step(1/60).roll,12);
 }
 a.move(1e10,-1e10,170);a.step(5);a.end();
 for(let i=0;i<600;i++){const p=a.step(1/60);expect(Math.abs(p.roll)).toBeLessThanOrEqual(5);expect(Math.abs(p.pitch)).toBeLessThanOrEqual(4);}
 expect(a.step(0)).toEqual({roll:0,pitch:0});
});
test('stationary pointer never starts a canned motion',()=>{
 const drag=new Rig2dDrag(contract);drag.begin(50,80);
 for(let i=0;i<200;i++){drag.move(50,80,170);expect(drag.step(1/60)).toEqual({roll:0,pitch:0});}
});
