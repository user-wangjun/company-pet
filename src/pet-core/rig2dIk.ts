const add=(a:number[],b:number[])=>a.map((v,i)=>v+b[i]);
const sub=(a:number[],b:number[])=>a.map((v,i)=>v-b[i]);
const mul=(a:number[],s:number)=>a.map(v=>v*s);
const dot=(a:number[],b:number[])=>a.reduce((s,v,i)=>s+v*b[i],0);
function unit(a:number[]):number[]{const n=Math.hypot(...a);if(!Number.isFinite(n)||n<1e-12)throw new Error("Ambiguous IK direction");return mul(a,1/n);}
const identity=()=>[[1,0,0],[0,1,0],[0,0,1]];
function align(from:number[],to:number[]):number[][]{
 const a=unit(from),b=unit(to),v=[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]],c=dot(a,b);
 if(c>1-1e-14)return identity();if(c<-.999999)throw new Error("Antiparallel IK branch");
 const k=[[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]];
 const kk=k.map(row=>k[0].map((_,j)=>row.reduce((s,v,i)=>s+v*k[i][j],0)));
 return k.map((row,i)=>row.map((v,j)=>(i===j?1:0)+v+kk[i][j]/(1+c)));
}

/** Fixed-length two-bone solve. An explicit rest pole selects the bend branch. */
export function solveRig2dTwoBone(root:number[],target:number[],restUpper:number[],restLower:number[],poleReference:number[]):{middle:number[];end:number[];upperRotation:number[][];lowerRotation:number[][]}{
 for(const v of [root,target,restUpper,restLower,poleReference])if(v.length!==3||!v.every(Number.isFinite))throw new Error("Invalid IK vector");
 const a=Math.hypot(...restUpper),b=Math.hypot(...restLower),delta=sub(target,root),distance=Math.hypot(...delta);
 if(a<=0||b<=0||distance>=a+b||distance<=Math.abs(a-b))throw new Error("IK target unreachable");
 const axis=unit(delta),pole=unit(sub(poleReference,mul(axis,dot(poleReference,axis))));
 const along=(a*a-b*b+distance*distance)/(2*distance),height=Math.sqrt(Math.max(0,a*a-along*along));
 const middle=add(add(root,mul(axis,along)),mul(pole,height));
 return {middle,end:[...target],upperRotation:align(restUpper,sub(middle,root)),lowerRotation:align(restLower,sub(target,middle))};
}
