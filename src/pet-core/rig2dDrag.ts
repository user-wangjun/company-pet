export type Rig2dDragContract = {
  action: string;
  frequency: number;
  damping: number;
  velocityGain: number;
  accelerationGain: number;
  channels: Record<string, { axis: 'x' | 'y'; gain: number }>;
  held?: Record<string, number>;
};
const clamp = (v: number, limit: number) => Math.max(-limit, Math.min(limit, v));

/** Pointer displacement in displayed body heights; never depends on window-local motion. */
export class Rig2dDrag {
  private point: [number, number] | null = null;
  private pending = [0, 0];
  private velocity = [0, 0];
  private offset = [0, 0];
  private speed = [0, 0];
  private accumulator = 0;
  active = false;
  get lateral(): number { return this.offset[0]; }
  constructor(readonly contract: Rig2dDragContract) {
    if (!contract.action || ![contract.frequency, contract.damping, contract.velocityGain, contract.accelerationGain].every(Number.isFinite)
      || contract.frequency <= 0 || contract.frequency > 30 || contract.damping <= 0
      || contract.velocityGain < 0 || contract.accelerationGain < 0
      || Object.values(contract.channels).some(c => !['x', 'y'].includes(c.axis) || !Number.isFinite(c.gain))
      || Object.values(contract.held??{}).some(v=>!Number.isFinite(v))) throw new Error('Invalid drag physics');
  }
  begin(x: number, y: number): void {
    if (![x,y].every(Number.isFinite)) return;
    this.point = [x,y]; this.pending = [0,0]; this.active = true;
  }
  move(x: number, y: number, height: number): void {
    if (!this.point || ![x,y,height].every(Number.isFinite) || height <= 0) return;
    this.pending[0] += (x-this.point[0])/height;
    this.pending[1] += (y-this.point[1])/height;
    this.point = [x,y];
  }
  end(): void { this.point = null; this.active = false; }
  step(seconds: number): Record<string, number> {
    if (!Number.isFinite(seconds) || seconds < 0) throw new Error('Invalid drag elapsed time');
    if (seconds > 0) {
      const dt = Math.min(seconds, .1), h = 1/120;
      const force = [0,0];
      for (let i=0;i<2;i++) {
        // A long frame discards stale pointer travel instead of generating a huge impulse.
        const target = seconds > .25 ? 0 : clamp(this.pending[i]/seconds, 8);
        const next = this.velocity[i] + (target-this.velocity[i])*(1-Math.exp(-18*dt));
        const acceleration = clamp((next-this.velocity[i])/dt, 40);
        force[i] = clamp(-next*this.contract.velocityGain-acceleration*this.contract.accelerationGain, 1);
        this.velocity[i] = next;
      }
      this.pending = [0,0]; this.accumulator += dt;
      while (this.accumulator+1e-12 >= h) {
        for (let i=0;i<2;i++) {
          const w=this.contract.frequency;
          this.speed[i] = clamp(this.speed[i]+(w*w*(force[i]-this.offset[i])-2*this.contract.damping*w*this.speed[i])*h, 12);
          this.offset[i] = clamp(this.offset[i]+this.speed[i]*h, 1);
          if (Math.abs(this.offset[i])===1 && this.offset[i]*this.speed[i]>0) this.speed[i]=0;
          if (!this.active && Math.abs(this.velocity[i])+Math.abs(this.offset[i])+Math.abs(this.speed[i])<1e-7) this.offset[i]=this.speed[i]=this.velocity[i]=0;
        }
        this.accumulator -= h;
      }
    }
    return Object.fromEntries(Object.entries(this.contract.channels).map(([id,c])=>[id,this.offset[c.axis==='x'?0:1]*c.gain]));
  }
}
