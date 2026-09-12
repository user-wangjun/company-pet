export type Rig2dParameterDefinition = { min: number; max: number; initial: number; frequency: number };
export type Rig2dParameterDefinitions = Record<string, Rig2dParameterDefinition>;
export type Rig2dParameterLayer = { values: Record<string, number>; weight: number; mode: "override" | "add" | "multiply" };
const clamp = (v: number, a: number, b: number) => Math.max(a, Math.min(b, v));

/** Model-independent, bounded continuous parameters. Target edits retain x/v. */
export class Rig2dParameters {
  readonly definitions: Rig2dParameterDefinitions;
  readonly state: Record<string, { value: number; velocity: number; target: number }>;

  constructor(definitions: Rig2dParameterDefinitions) {
    for (const [id, d] of Object.entries(definitions)) {
      if (!id || ![d.min,d.max,d.initial,d.frequency].every(Number.isFinite) || d.min > d.max || d.initial < d.min || d.initial > d.max || d.frequency <= 0) {
        throw new Error("Invalid rig parameter definition: " + id);
      }
    }
    this.definitions = Object.fromEntries(Object.entries(definitions).map(([id,d]) => [id,{...d}]));
    this.state = Object.fromEntries(Object.entries(definitions).map(([id,d]) => [id,{value:d.initial,velocity:0,target:d.initial}]));
  }

  setTargets(targets: Record<string, number>): void {
    // Validate the whole change first; bad action data cannot partially apply.
    for (const [id,v] of Object.entries(targets)) {
      if (!Object.prototype.hasOwnProperty.call(this.definitions,id) || !Number.isFinite(v)) throw new Error("Invalid rig parameter: " + id);
    }
    for (const [id,v] of Object.entries(targets)) {
      const d=this.definitions[id]; this.state[id].target=clamp(v,d.min,d.max);
    }
  }

  setLayers(layers: Rig2dParameterLayer[]): void {
    const targets=Object.fromEntries(Object.entries(this.definitions).map(([id,d]) => [id,d.initial]));
    for (const layer of layers) {
      if (!Number.isFinite(layer.weight) || layer.weight < 0 || layer.weight > 1 || !["override","add","multiply"].includes(layer.mode)) throw new Error("Invalid parameter layer");
      for (const [id,v] of Object.entries(layer.values)) {
        if (!Object.prototype.hasOwnProperty.call(targets,id) || !Number.isFinite(v)) throw new Error("Invalid layer parameter: " + id);
        const w=layer.weight;
        targets[id]=layer.mode === "override" ? targets[id]+(v-targets[id])*w : layer.mode === "add" ? targets[id]+v*w : targets[id]*(1+(v-1)*w);
      }
    }
    this.setTargets(targets);
  }

  values(): Record<string, number> { return Object.fromEntries(Object.entries(this.state).map(([id,s]) => [id,s.value])); }

  step(seconds: number): Record<string, number> {
    if (!Number.isFinite(seconds) || seconds < 0) throw new Error("Invalid elapsed time");
    for (const [id,s] of Object.entries(this.state)) {
      const d=this.definitions[id],w=d.frequency,x=s.value-s.target,c=s.velocity+w*x,e=Math.exp(-w*seconds);
      // Exact critically damped response, independent of render substeps.
      s.value=s.target+(x+c*seconds)*e; s.velocity=(s.velocity-w*c*seconds)*e;
      if (s.value < d.min || s.value > d.max) {
        s.value=clamp(s.value,d.min,d.max);
        if ((s.value===d.min && s.velocity<0) || (s.value===d.max && s.velocity>0)) s.velocity=0;
      }
      if (Math.abs(s.value-s.target)<1e-10 && Math.abs(s.velocity)<1e-10) {s.value=s.target;s.velocity=0;}
    }
    return this.values();
  }
}
