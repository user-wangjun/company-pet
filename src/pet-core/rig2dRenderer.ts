import { Assets, Container, Mesh, MeshGeometry, RenderTexture, Sprite } from "pixi.js";
import { createRig2dDetailShader } from "./rig2dDetailShader";
import type { Shader } from "pixi.js";
import type { Renderer } from "pixi.js";
import type { LoadedRig2dMesh, Rig2dMeshData } from "./rig2dAssets";

type RigMask={container:Container;target:RenderTexture;sprite:Sprite;mesh:Mesh;geometry:MeshGeometry;requestedResolution:number};

/** Generic rendering only: package-specific motion is supplied by the caller. */
export class Rig2dRenderer {
  readonly container = new Container();
  private entries: { data: Rig2dMeshData; mesh: Mesh; geometry: MeshGeometry }[] = [];
  private masks = new Map<string,RigMask>();
  private destroyed = false;
  private detailShaders: Shader[] = [];
  private readonly maxMaskEdge: number;
  private constructor(private renderer: Renderer) {
    this.maxMaskEdge = "gl" in renderer
      ? Math.min(4096, renderer.gl.getParameter(renderer.gl.MAX_TEXTURE_SIZE))
      : 4096;
  }

  static async create(renderer: Renderer, canvas: number[], materials: LoadedRig2dMesh[]): Promise<Rig2dRenderer> {
    const rig = new Rig2dRenderer(renderer);
    try {
      // Fetch concurrently, then allocate owned GPU resources sequentially so
      // a failed load cannot leave late allocations after cleanup.
      const textures = await Promise.all(materials.map(m => Assets.load(m.textureUrl)));
      const details = await Promise.all(materials.map(m => m.detailTextureUrl ? Assets.load(m.detailTextureUrl) : Promise.resolve(null)));
      for (let i = 0; i < materials.length; i++) {
        const data = materials[i].data, texture = textures[i]; texture.source.scaleMode = "linear";
        const geometry = new MeshGeometry({ positions: new Float32Array(data.positions.flat()), uvs: new Float32Array(data.uvs.flat()), indices: new Uint32Array(data.indices) });
        const mesh=new Mesh({geometry,texture,label:data.id});
        rig.entries.push({data,geometry,mesh});
        if(details[i] && data.colourDetail){
          if(!("gl" in renderer))throw new Error("Rig colour detail requires WebGL");
          details[i].source.scaleMode="linear";
          const shader=createRig2dDetailShader(texture,details[i],canvas,data.colourDetail.sourceRectangle);
          rig.detailShaders.push(shader);mesh.shader=shader;
        }
      }
      for (const entry of rig.entries.filter(e => e.data.isClippingMask)) {
        const container = new Container(); container.addChild(entry.mesh);
        const target = RenderTexture.create({ width: 1, height: 1, resolution: renderer.resolution, dynamic: true });
        const sprite = new Sprite(target); rig.container.addChild(sprite);
        const mask={container,target,sprite,mesh:entry.mesh,geometry:entry.geometry,requestedResolution:renderer.resolution};
        rig.masks.set(entry.data.id,mask);rig.placeMaskTarget(mask);
      }
      for (const entry of rig.entries.filter(e => !e.data.isClippingMask).sort((a,b) => a.data.drawOrder-b.data.drawOrder)) {
        rig.container.addChild(entry.mesh);
        if (entry.data.clipping) {
          const mask = rig.masks.get(entry.data.clipping.mask);
          if (!mask) throw new Error("Missing rig mask");
          entry.mesh.setMask({ mask: mask.sprite, channel: "red", inverse: entry.data.clipping.mode === "outside" });
        }
      }
      return rig;
    } catch (error) { rig.destroy(); throw error; }
  }

  /** Match offscreen eye coverage to display scale without changing model UVs. */
  setMaskResolution(resolution: number): void {
    if (this.destroyed) throw new Error("Rig renderer destroyed");
    if (!Number.isFinite(resolution) || resolution <= 0) throw new Error("Invalid mask resolution");
    for (const mask of this.masks.values()) {
      mask.requestedResolution=resolution;this.placeMaskTarget(mask);
    }
  }

  private placeMaskTarget(mask:RigMask):void{
    const p=mask.geometry.positions;
    let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    for(let i=0;i<p.length;i+=2){minX=Math.min(minX,p[i]);maxX=Math.max(maxX,p[i]);minY=Math.min(minY,p[i+1]);maxY=Math.max(maxY,p[i+1]);}
    if(!Number.isFinite(minX+minY+maxX+maxY))throw new Error('Empty rig mask');
    const resolution=Math.min(mask.requestedResolution,(this.maxMaskEdge-32)/Math.max(1,maxX-minX,maxY-minY));
    // Two transparent physical pixels keep linear sampling outside the local
    // texture at zero, including inverse eyelid masks. Match the full-canvas
    // pixel lattice exactly instead of following fractional mesh bounds.
    const x=(Math.floor(minX*resolution)-2)/resolution,y=(Math.floor(minY*resolution)-2)/resolution;
    const pixelsX=Math.ceil((Math.ceil(maxX*resolution)-Math.floor(minX*resolution)+4)/16)*16;
    const pixelsY=Math.ceil((Math.ceil(maxY*resolution)-Math.floor(minY*resolution)+4)/16)*16;
    const densityChanged=Math.abs(mask.target.source.resolution-resolution)>1e-6;
    const width=densityChanged?pixelsX:Math.max(pixelsX,mask.target.source.pixelWidth);
    const height=densityChanged?pixelsY:Math.max(pixelsY,mask.target.source.pixelHeight);
    if(densityChanged||width!==mask.target.source.pixelWidth||height!==mask.target.source.pixelHeight)mask.target.resize(width/resolution,height/resolution,resolution);
    mask.container.position.set(-x,-y);mask.sprite.position.set(x,y);
    mask.sprite.width=width/resolution;mask.sprite.height=height/resolution;
  }

  get detailMaterialCount(): number { return this.detailShaders.length; }

  getMaskSampling(): { resolution: number; width: number; height: number }[] {
    return [...this.masks.values()].map(({ target }) => ({
      resolution: target.source.resolution,
      width: target.source.pixelWidth,
      height: target.source.pixelHeight,
    }));
  }

  update(deform: (mesh: Rig2dMeshData) => number[][], maskEnabled: (id: string) => boolean = () => true, materialVisible: (id: string) => boolean = () => true): void {
    this.updateInto((mesh,target)=>{
      const points=deform(mesh);
      if(points.length!==mesh.positions.length)throw new Error("Invalid rig pose");
      for(let i=0;i<points.length;i++){
        const p=points[i];if(p.length!==2||!Number.isFinite(p[0])||!Number.isFinite(p[1]))throw new Error("Invalid rig pose");
        target[i*2]=p[0];target[i*2+1]=p[1];
      }
    },maskEnabled,materialVisible);
  }

  private poseBuffers = new Map<Rig2dMeshData,Float32Array>();

  updateInto(deform: (mesh: Rig2dMeshData,target:Float32Array) => void, maskEnabled: (id: string) => boolean = () => true, materialVisible: (id: string) => boolean = () => true): void {
    if (this.destroyed) throw new Error("Rig renderer destroyed");
    // Stage and validate the entire pose before changing any GPU buffer.
    // NaN also catches callbacks that leave a vertex unwritten this frame.
    const poses = this.entries.map(e => {
      let buffer=this.poseBuffers.get(e.data);
      if(!buffer){buffer=new Float32Array(e.data.positions.length*2);this.poseBuffers.set(e.data,buffer);}
      buffer.fill(NaN);deform(e.data,buffer);
      for(let i=0;i<buffer.length;i++)if(!Number.isFinite(buffer[i]))throw new Error("Invalid rig pose");
      return buffer;
    });
    this.entries.forEach((entry, index) => {
      if (!entry.data.isClippingMask) entry.mesh.visible = materialVisible(entry.data.id);
      const positions = entry.geometry.positions;
      positions.set(poses[index]);
      entry.geometry.getBuffer("aPosition").update();
    });
    for (const [id, mask] of this.masks) {
      this.placeMaskTarget(mask);
      mask.mesh.visible = maskEnabled(id);
      this.renderer.render({ container: mask.container, target: mask.target, clear: true });
    }
  }

  destroy(): void {
    if (this.destroyed) return; this.destroyed = true;
    for (const entry of this.entries) { entry.mesh.setMask({ mask: null }); entry.mesh.destroy(); entry.geometry.destroy(); }
    for (const mask of this.masks.values()) {
      mask.container.destroy(); mask.sprite.destroy();
      // Pixi's shared alpha-mask filter pool still references the source until
      // its next use. Destroying it poisons the pooled BindGroup. Release GPU
      // storage now, but let the detached source be collected after rebinding.
      mask.target.source.unload();
      mask.target.destroy(false);
    }
    for (const shader of this.detailShaders) shader.destroy();
    this.detailShaders=[];
    this.container.destroy(); this.entries = []; this.masks.clear(); this.poseBuffers.clear();
  }
}
