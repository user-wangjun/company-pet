import {expect,test,vi} from 'vitest';
import {Rig2dRenderer} from './rig2dRenderer';

function fixture(){
 const entries=['a','b'].map(id=>({data:{id,positions:[[0,0],[1,0],[0,1]],isClippingMask:false},mesh:{visible:true},geometry:{positions:new Float32Array([0,0,1,0,0,1]),getBuffer:()=>({update:upload})}}));
 const upload=vi.fn();
 // Exercise buffer transaction logic without mocking the implementation or GPU.
 const rig=Object.assign(Object.create(Rig2dRenderer.prototype),{entries,poseBuffers:new Map(),masks:new Map(),destroyed:false}) as Rig2dRenderer;
 return {rig,entries,upload};
}

test('a partial later material does not commit any GPU pose, and the next full update recovers',()=>{
 const {rig,entries,upload}=fixture();
 expect(()=>rig.updateInto((mesh,out)=>{if(mesh.id==='a')out.fill(9);else out[0]=5;})).toThrow('Invalid rig pose');
 expect(upload).not.toHaveBeenCalled();
 for(const e of entries)expect([...e.geometry.positions]).toEqual([0,0,1,0,0,1]);
 rig.updateInto((mesh,out)=>out.fill(mesh.id==='a'?2:3));
 expect([...entries[0].geometry.positions]).toEqual([2,2,2,2,2,2]);
 expect([...entries[1].geometry.positions]).toEqual([3,3,3,3,3,3]);expect(upload).toHaveBeenCalledTimes(2);
});

test('legacy array callbacks retain validation and reject float32 overflow before upload',()=>{
 const {rig,entries,upload}=fixture();
 expect(()=>rig.update(()=>[[Number.MAX_VALUE,0],[1,0],[0,1]])).toThrow('Invalid rig pose');
 expect(upload).not.toHaveBeenCalled();
 rig.update(mesh=>mesh.positions.map(([x,y])=>[x+1,y+2]));
 expect([...entries[0].geometry.positions]).toEqual([1,2,2,2,1,3]);
});
