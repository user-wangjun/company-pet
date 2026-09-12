export type Rig2dEyeShape = {
 role: string; upper: number[][]; lower: number[][]; gazeRange: number[];
};
const clamp=(x:number,a:number,b:number)=>Math.max(a,Math.min(b,x));
function curveY(points:number[][],x:number):number {
 const cubic=(t:number,k:number)=>(1-t)**3*points[0][k]+3*(1-t)**2*t*points[1][k]+3*(1-t)*t*t*points[2][k]+t**3*points[3][k];
 x=clamp(x,points[0][0],points[3][0]);let lo=0,hi=1;
 for(let i=0;i<24;i++){const mid=(lo+hi)/2;if(cubic(mid,0)<x)lo=mid;else hi=mid;}
 return cubic((lo+hi)/2,1);
}

/** Shape coordinates and motion ranges come from the pet's material contract. */
export function deformRig2dEye(x:number,y:number,shape:Rig2dEyeShape,open:number,gaze:number[]):number[]{
 if(![x,y,open,...gaze].every(Number.isFinite)||gaze.length!==2||open<0||open>1)throw new Error("Invalid eye deformation input");
 const close=1-open,role=shape.role;
 if(role==="iris"||role==="pupil"||role==="highlight")return [x+gaze[0]*shape.gazeRange[0],y+gaze[1]*shape.gazeRange[1]];
 if(close>0){
  const top=curveY(shape.upper,x),bottom=curveY(shape.lower,x),height=Math.max(.01,bottom-top);
  if(role==="lid.upper")y+=height*.85*close*Math.exp(-Math.max(0,top-y)/12);
  if(role==="lid.lower")y-=height*.15*close*Math.exp(-Math.max(0,y-bottom)/12);
  // Keep a positive evaluation cage; the renderer disables closed apertures.
  if(role==="eye.mask")y=top+height*.85*close+(y-top)*Math.max(.005,open);
 }
 return [x,y];
}

export function deformRig2dBreath(x:number,y:number,shape:{centre:number[];radiusY:number;radialGain:number},amount:number):number[]{
 const gain=Math.exp(-(((y-shape.centre[1])/shape.radiusY)**2))*amount;
 return [x+(x-shape.centre[0])*shape.radialGain*gain,y];
}

/** A compact C1 depth cap avoids an infinite slope at a projected skull rim. */
export function rig2dDepthCap(x:number,y:number,centre:number[],radii:number[],hemisphere:number):number{
 const q=((x-centre[0])/radii[0])**2+((y-centre[1])/radii[1])**2;
 const cap=Math.max(0,1-q);return centre[2]+hemisphere*radii[2]*cap*cap;
}

export type Rig2dFaceSurface={centreX:number;blendY:[number,number];sections:Array<{y:number;halfWidth:number;centreDepth:number;edgeDepth:number}>};
type FaceField='halfWidth'|'centreDepth'|'edgeDepth';
const faceSlopeCache=new WeakMap<Rig2dFaceSurface,Record<FaceField,number[]>>();
function faceSlopes(profile:Rig2dFaceSurface):Record<FaceField,number[]>{
 let result=faceSlopeCache.get(profile);if(result)return result;
 const s=profile.sections;result={} as Record<FaceField,number[]>;
 for(const field of ['halfWidth','centreDepth','edgeDepth'] as const){
  const h=s.slice(1).map((v,i)=>v.y-s[i].y),d=h.map((v,i)=>(s[i+1][field]-s[i][field])/v);
  result[field]=s.map((_,i)=>{if(i===0||i===s.length-1)return 0;if(d[i-1]*d[i]<=0)return 0;
   const a=2*h[i]+h[i-1],b=h[i]+2*h[i-1];return (a+b)/(a/d[i-1]+b/d[i]);});
 }
 faceSlopeCache.set(profile,result);return result;
}

/** Source-coordinate facial sections; all eye layers sample the same surface. */
export function rig2dFaceSurfaceDepth(x:number,y:number,baseDepth:number,profile:Rig2dFaceSurface):number{
 const sections=profile.sections;
 let a=sections[0],b=a,index=0;
 for(let i=1;i<sections.length;i++){b=sections[i];if(y<=b.y)break;a=b;index=i;}
 const t=a===b?0:clamp((y-a.y)/(b.y-a.y),0,1);
 const slopes=faceSlopes(profile),span=b.y-a.y;
 const sample=(field:FaceField)=>a===b?a[field]:(2*t**3-3*t*t+1)*a[field]+(t**3-2*t*t+t)*span*slopes[field][index]+(-2*t**3+3*t*t)*b[field]+(t**3-t*t)*span*slopes[field][index+1];
 const width=sample('halfWidth'),centre=sample('centreDepth'),edge=sample('edgeDepth');
 const u=Math.abs(x-profile.centreX)/width;
 // Rounded cross section with a zero tangent at both the centre and rim.
 // A narrow rim transition produces an artificial ridge in combined turns.
 const cap=Math.max(0,1-u*u),shape=cap*cap;
 const blend=clamp((y-profile.blendY[0])/(profile.blendY[1]-profile.blendY[0]),0,1),w=blend*blend*(3-2*blend);
 return baseDepth+(edge+(centre-edge)*shape-baseDepth)*w;
}
