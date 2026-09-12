import {Shader,Texture,compileHighShaderGlProgram,localUniformBitGl,roundPixelsBitGl} from 'pixi.js';
/** Colour detail uses its own resolution; silhouette always uses the base alpha. */
export function createRig2dDetailShader(base:Texture,detail:Texture,canvas:number[],rectangle:number[],premultipliedDetail=false):Shader & {texture:Texture} {
 const [x0,y0,x1,y1]=rectangle;
 const shader=new Shader({glProgram:compileHighShaderGlProgram({name:'rig-colour-detail',bits:[localUniformBitGl,roundPixelsBitGl,{name:'rig-detail',fragment:{header:'uniform sampler2D uBase; uniform sampler2D uDetail; uniform vec4 uDetailRegion; uniform vec2 uCanvas;',main:`
 vec4 baseSample=texture(uBase,vUV);
 vec2 detailUV=(vUV*uCanvas-uDetailRegion.xy)/uDetailRegion.zw;
 vec4 detailSample=texture(uDetail,detailUV);
 // RGBA colour sources are premultiplied on upload. Recover straight colour
 // before applying the authoritative base alpha, otherwise overlap rims darken.
 vec3 detail=${premultipliedDetail?'detailSample.a>0.0?detailSample.rgb/detailSample.a:baseSample.rgb/max(baseSample.a,0.000001)':'detailSample.rgb'};
 outColor=vec4(detail*baseSample.a,baseSample.a);
`}}]}),resources:{uBase:base.source,uDetail:detail.source,detailUniforms:{uDetailRegion:{type:'vec4<f32>',value:[x0,y0,x1-x0,y1-y0]},uCanvas:{type:'vec2<f32>',value:canvas}}}});
 return Object.assign(shader,{texture:base});
}
