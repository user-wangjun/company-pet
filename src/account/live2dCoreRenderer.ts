import type { AccountPetParameters } from "./accountPetParameters";

type CubismMoc = { _release: () => void };
type CubismModel = {
  canvasinfo: {
    CanvasHeight: number;
    CanvasOriginX: number;
    CanvasOriginY: number;
    CanvasWidth: number;
  };
  drawables: {
    blendModes: Int32Array;
    count: number;
    ids: string[];
    indexCounts: Int32Array;
    indices: Uint16Array[];
    multiplyColors: Float32Array;
    opacities: Float32Array;
    screenColors: Float32Array;
    textureIndices: Int32Array;
    vertexPositions: Float32Array[];
    vertexUvs: Float32Array[];
  };
  parameters: {
    count: number;
    ids: string[];
    maximumValues: Float32Array;
    minimumValues: Float32Array;
    values: Float32Array;
  };
  getRenderOrders: () => Int32Array;
  release: () => void;
  update: () => void;
};

type CubismCore = {
  ColorBlendType_Add: number;
  ColorBlendType_Multiply: number;
  Memory: { initializeAmountOfMemory: (bytes: number) => void };
  Moc: { fromArrayBuffer: (bytes: ArrayBuffer) => CubismMoc | null };
  Model: { fromMoc: (moc: CubismMoc) => CubismModel | null };
};

declare global {
  interface Window {
    Live2DCubismCore?: CubismCore;
  }
}

const CORE_URL = "/vendor/live2d-cubism-core/live2dcubismcore.min.js";
let corePromise: Promise<CubismCore> | null = null;

function loadCore(): Promise<CubismCore> {
  if (window.Live2DCubismCore) return Promise.resolve(window.Live2DCubismCore);
  if (corePromise) return corePromise;

  corePromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${CORE_URL}"]`);
    const script = existing ?? document.createElement("script");
    const finish = () => {
      const core = window.Live2DCubismCore;
      if (core) resolve(core);
      else reject(new Error("Live2D Cubism Core loaded without a global API"));
    };
    script.addEventListener("load", finish, { once: true });
    script.addEventListener("error", () => reject(new Error("Unable to load Live2D Cubism Core")), { once: true });
    if (!existing) {
      script.async = true;
      script.src = CORE_URL;
      document.head.appendChild(script);
    }
  });

  return corePromise;
}

const VERTEX_SHADER = `
attribute vec2 a_position;
attribute vec2 a_texCoord;
uniform vec2 u_scale;
uniform vec2 u_offset;
uniform vec2 u_pivot;
uniform float u_rotation;
uniform float u_catScale;
varying vec2 v_texCoord;
void main() {
  vec2 p = u_pivot + ((a_position - u_pivot) * u_catScale);
  float c = cos(u_rotation);
  float s = sin(u_rotation);
  p = u_pivot + mat2(c, -s, s, c) * (p - u_pivot);
  gl_Position = vec4((p * u_scale) + u_offset, 0.0, 1.0);
  v_texCoord = vec2(a_texCoord.x, 1.0 - a_texCoord.y);
}`;

const FRAGMENT_SHADER = `
precision mediump float;
varying vec2 v_texCoord;
uniform sampler2D u_texture;
uniform vec4 u_baseColor;
uniform vec4 u_multiplyColor;
uniform vec4 u_screenColor;
void main() {
  vec4 color = texture2D(u_texture, v_texCoord);
  color.rgb *= u_multiplyColor.rgb;
  color.rgb = (color.rgb + (u_screenColor.rgb * color.a)) - (color.rgb * u_screenColor.rgb);
  gl_FragColor = color * u_baseColor;
}`;

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("Unable to allocate a Live2D shader");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader) ?? "Unable to compile a Live2D shader");
  }
  return shader;
}

function createProgram(gl: WebGLRenderingContext): WebGLProgram {
  const program = gl.createProgram();
  if (!program) throw new Error("Unable to allocate a Live2D WebGL program");
  gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER));
  gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program) ?? "Unable to link the Live2D WebGL program");
  }
  return program;
}

function loadTexture(gl: WebGLRenderingContext, url: string): Promise<WebGLTexture> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => {
      const texture = gl.createTexture();
      if (!texture) {
        reject(new Error("Unable to allocate the Live2D texture"));
        return;
      }
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, 1);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      resolve(texture);
    };
    image.onerror = () => reject(new Error(`Unable to load Live2D texture: ${url}`));
    image.src = url;
  });
}

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));
const smoothstep = (edge0: number, edge1: number, value: number) => {
  const t = clamp((value - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - (2 * t));
};

export class Live2DPlanetScene {
  static async create(canvas: HTMLCanvasElement, modelBaseUrl: string): Promise<Live2DPlanetScene> {
    const core = await loadCore();
    core.Memory.initializeAmountOfMemory(32 * 1024 * 1024);
    const response = await fetch(`${modelBaseUrl}/xiaoju-planet-login.moc3`);
    if (!response.ok) throw new Error(`Unable to load Live2D moc3 (${response.status})`);
    const moc = core.Moc.fromArrayBuffer(await response.arrayBuffer());
    if (!moc) throw new Error("Live2D rejected the exported moc3");
    const model = core.Model.fromMoc(moc);
    if (!model) {
      moc._release();
      throw new Error("Live2D could not instantiate the exported model");
    }

    const gl = canvas.getContext("webgl", {
      alpha: true,
      antialias: true,
      premultipliedAlpha: true,
    });
    if (!gl) {
      model.release();
      moc._release();
      throw new Error("WebGL is unavailable for the Live2D scene");
    }

    const program = createProgram(gl);
    const texture = await loadTexture(
      gl,
      `${modelBaseUrl}/xiaoju-planet-login.2048/texture_00.png`,
    );
    return new Live2DPlanetScene(core, canvas, gl, moc, model, program, texture);
  }

  private readonly parameterIndices = new Map<string, number>();
  private readonly drawableIndices: number[];
  private readonly positionBuffer: WebGLBuffer;
  private readonly uvBuffer: WebGLBuffer;
  private readonly indexBuffer: WebGLBuffer;
  private readonly sceneBounds: { minX: number; minY: number; maxX: number; maxY: number };
  private readonly facePivot: [number, number];
  private disposed = false;

  private constructor(
    private readonly core: CubismCore,
    private readonly canvas: HTMLCanvasElement,
    private readonly gl: WebGLRenderingContext,
    private readonly moc: CubismMoc,
    private readonly model: CubismModel,
    private readonly program: WebGLProgram,
    private readonly texture: WebGLTexture,
  ) {
    model.parameters.ids.forEach((id, index) => this.parameterIndices.set(id, index));
    this.drawableIndices = Array.from({ length: model.drawables.count }, (_, index) => index);
    this.sceneBounds = this.measureBounds(this.drawableIndices);
    const eyeIndices = this.drawableIndices.filter((index) => /Eye_[LR]_Base/i.test(model.drawables.ids[index]));
    const eyeBounds = eyeIndices.length ? this.measureBounds(eyeIndices) : this.sceneBounds;
    this.facePivot = [(eyeBounds.minX + eyeBounds.maxX) / 2, (eyeBounds.minY + eyeBounds.maxY) / 2];
    const positionBuffer = gl.createBuffer();
    const uvBuffer = gl.createBuffer();
    const indexBuffer = gl.createBuffer();
    if (!positionBuffer || !uvBuffer || !indexBuffer) throw new Error("Unable to allocate Live2D mesh buffers");
    this.positionBuffer = positionBuffer;
    this.uvBuffer = uvBuffer;
    this.indexBuffer = indexBuffer;
  }

  private measureBounds(indices: number[]) {
    let minX = Number.POSITIVE_INFINITY;
    let minY = Number.POSITIVE_INFINITY;
    let maxX = Number.NEGATIVE_INFINITY;
    let maxY = Number.NEGATIVE_INFINITY;
    indices.forEach((index) => {
      const positions = this.model.drawables.vertexPositions[index];
      for (let cursor = 0; cursor < positions.length; cursor += 2) {
        minX = Math.min(minX, positions[cursor]);
        maxX = Math.max(maxX, positions[cursor]);
        minY = Math.min(minY, positions[cursor + 1]);
        maxY = Math.max(maxY, positions[cursor + 1]);
      }
    });
    return { minX, minY, maxX, maxY };
  }

  private setParameter(id: string, value: number) {
    const index = this.parameterIndices.get(id);
    if (index === undefined) return;
    this.model.parameters.values[index] = clamp(
      value,
      this.model.parameters.minimumValues[index],
      this.model.parameters.maximumValues[index],
    );
  }

  render(parameters: AccountPetParameters, elapsedSeconds: number, blink: number) {
    if (this.disposed) return;
    this.setParameter("ParamEyeBallX", parameters.eyeBallX);
    this.setParameter("ParamEyeBallY", parameters.eyeBallY);
    this.setParameter("ParamEyeLOpen", 1 - blink);
    this.setParameter("ParamEyeROpen", 1 - blink);
    this.setParameter("ParamEyeLSmile", smoothstep(0, .78, parameters.pawCover));
    this.setParameter("ParamEyeRSmile", smoothstep(.12, 1, parameters.pawCover));
    this.setParameter("ParamMouthForm", parameters.mouthForm);
    this.setParameter("ParamBreath", .5 + (Math.sin(elapsedSeconds * 1.65) * .18));
    this.setParameter("ParamPawCover", parameters.pawCover);
    this.model.update();
    this.draw(parameters.angleZ, blink, elapsedSeconds);
  }

  private draw(angleZ: number, blink: number, elapsedSeconds: number) {
    const { gl, canvas, model } = this;
    const width = Math.max(1, Math.round(canvas.clientWidth * Math.min(2, window.devicePixelRatio || 1)));
    const height = Math.max(1, Math.round(canvas.clientHeight * Math.min(2, window.devicePixelRatio || 1)));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }

    gl.viewport(0, 0, width, height);
    gl.clearColor(0.025, 0.075, 0.32, 1);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.disable(gl.CULL_FACE);
    gl.disable(gl.DEPTH_TEST);
    gl.enable(gl.BLEND);
    gl.useProgram(this.program);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.uniform1i(gl.getUniformLocation(this.program, "u_texture"), 0);

    const bounds = this.sceneBounds;
    const modelWidth = bounds.maxX - bounds.minX;
    const modelHeight = bounds.maxY - bounds.minY;
    const pixelsPerUnit = Math.max(width / modelWidth, height / modelHeight);
    const scaleX = (2 * pixelsPerUnit) / width;
    const scaleY = (2 * pixelsPerUnit) / height;
    const centerX = (bounds.minX + bounds.maxX) / 2;
    const centerY = (bounds.minY + bounds.maxY) / 2;
    gl.uniform2f(gl.getUniformLocation(this.program, "u_scale"), scaleX, scaleY);
    gl.uniform2f(gl.getUniformLocation(this.program, "u_offset"), -centerX * scaleX, -centerY * scaleY);
    gl.uniform2f(gl.getUniformLocation(this.program, "u_pivot"), this.facePivot[0], this.facePivot[1]);

    const drawables = model.drawables;
    const renderOrders = model.getRenderOrders();
    this.drawableIndices.sort((left, right) => renderOrders[left] - renderOrders[right]);

    for (const index of this.drawableIndices) {
      const id = drawables.ids[index];
      if (/^Paw_[LR]$|Rest_Paw|Cover_Foreleg|Foreleg_[LR]_Complete|Shoulder_Occluder/i.test(id)) continue;
      const isScenePlate = /Stars_Background|Planet_Foreground/i.test(id);
      const isEyelid = /Eyelid/i.test(id);
      const isOpenEye = /Eye_[LR]_Base|Pupil_[LR]/i.test(id);
      let opacity = drawables.opacities[index];
      if (isEyelid) opacity *= blink;
      if (isOpenEye) opacity *= 1 - blink;
      if (opacity <= .002) continue;

      const rotation = isScenePlate ? 0 : (angleZ * Math.PI / 180) * .58;
      const breathScale = isScenePlate ? 1 : 1 + (Math.sin(elapsedSeconds * 1.65) * .0025);
      gl.uniform1f(gl.getUniformLocation(this.program, "u_rotation"), rotation);
      gl.uniform1f(gl.getUniformLocation(this.program, "u_catScale"), breathScale);

      const multiplyOffset = index * 4;
      gl.uniform4fv(
        gl.getUniformLocation(this.program, "u_multiplyColor"),
        drawables.multiplyColors.subarray(multiplyOffset, multiplyOffset + 4),
      );
      gl.uniform4fv(
        gl.getUniformLocation(this.program, "u_screenColor"),
        drawables.screenColors.subarray(multiplyOffset, multiplyOffset + 4),
      );
      gl.uniform4f(gl.getUniformLocation(this.program, "u_baseColor"), opacity, opacity, opacity, opacity);

      const blendMode = drawables.blendModes[index];
      if (blendMode === this.core.ColorBlendType_Add) gl.blendFunc(gl.ONE, gl.ONE);
      else if (blendMode === this.core.ColorBlendType_Multiply) gl.blendFunc(gl.DST_COLOR, gl.ONE_MINUS_SRC_ALPHA);
      else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);

      gl.bindBuffer(gl.ARRAY_BUFFER, this.positionBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, drawables.vertexPositions[index], gl.DYNAMIC_DRAW);
      const positionLocation = gl.getAttribLocation(this.program, "a_position");
      gl.enableVertexAttribArray(positionLocation);
      gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

      gl.bindBuffer(gl.ARRAY_BUFFER, this.uvBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, drawables.vertexUvs[index], gl.STATIC_DRAW);
      const uvLocation = gl.getAttribLocation(this.program, "a_texCoord");
      gl.enableVertexAttribArray(uvLocation);
      gl.vertexAttribPointer(uvLocation, 2, gl.FLOAT, false, 0, 0);

      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.indexBuffer);
      gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, drawables.indices[index], gl.STATIC_DRAW);
      gl.drawElements(gl.TRIANGLES, drawables.indexCounts[index], gl.UNSIGNED_SHORT, 0);
    }
  }

  destroy() {
    if (this.disposed) return;
    this.disposed = true;
    this.gl.deleteBuffer(this.positionBuffer);
    this.gl.deleteBuffer(this.uvBuffer);
    this.gl.deleteBuffer(this.indexBuffer);
    this.gl.deleteTexture(this.texture);
    this.gl.deleteProgram(this.program);
    this.model.release();
    this.moc._release();
  }
}
