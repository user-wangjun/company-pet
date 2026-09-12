import { expect, test } from "vitest";
import { Rig2dModel, type Rig2dModelContract } from "./rig2dModel";
import type { Rig2dMeshData } from "./rig2dAssets";

function modelContract(): Rig2dModelContract {
  return {
    schemaVersion: 1, origin: [100, 100, 0],
    nodes: [
      { id: "hip", parent: null, restOffset: [0, 0, 0], restPosition: [0, 0, 0] },
      { id: "knee", parent: "hip", restOffset: [0, 1, 0], restPosition: [0, 1, 0] },
      { id: "foot", parent: "knee", restOffset: [0, 1, 0], restPosition: [0, 2, 0] },
    ],
    parameters: { rootX: { min: -0.5, max: 0.5, initial: 0, frequency: 12 }, turn: { min: -90, max: 90, initial: 0, frequency: 12 } },
    bindings: [{ joint: "hip", parameter: "turn", axis: "z" }], translation: ["rootX", null, null],
    ik: [{ upper: "hip", middle: "knee", end: "foot", pole: [1, 0, 0], descendants: [] }],
    materials: { foot: { joints: ["foot"] } }, apertures: {},
  };
}

test("buffered deformation invalidates cached depth when local coordinates change", () => {
  const contract=modelContract();
  contract.parameters.breath={min:0,max:1,initial:0,frequency:12};
  contract.materials.foot.depth={centre:[100,102,0],radii:[4,4,2],hemisphere:1};
  contract.materials.foot.local={kind:'breath',parameter:'breath',centre:[100,102],radiusY:10,radialGain:.5};
  const model=new Rig2dModel(contract),mesh:Rig2dMeshData={id:'foot',positions:[[101,102]],uvs:[[0,0]],indices:[],drawOrder:1,texture:'body.png',mask:'',isClippingMask:false,clipping:null};
  const out=new Float32Array(2);
  for(const amount of [0,1,0]){
    model.deformInto(mesh,model.pose({breath:amount},{}),out,1);
    const x=101+.5*amount,depth=2*(1-((x-100)/4)**2)**2;
    expect([...out]).toEqual([Math.fround(x),Math.fround(102+depth)]);
  }
  mesh.positions[0][0]=102;
  model.deformInto(mesh,model.pose({},{}),out,1);
  expect([...out]).toEqual([102,103.125]);
  expect(()=>model.deformInto(mesh,model.pose({},{}),new Float32Array(3))).toThrow('buffer');
});

test("room contacts solve a real endpoint with fixed bone lengths across 41 poses", () => {
  const model = new Rig2dModel(modelContract());
  for (let i = 0; i <= 40; i++) {
    const x = 0.2 * Math.sin(i * Math.PI / 20);
    const pose = model.pose({ rootX: x }, { foot: [0.5, 1.5, 0] });
    expect(pose.positions.foot).toEqual([0.5, 1.5, 0]);
    for (const [a, b] of [["hip", "knee"], ["knee", "foot"]]) {
      expect(Math.hypot(...pose.positions[a].map((p, axis) => p - pose.positions[b][axis]))).toBeCloseTo(1, 10);
    }
    expect(pose.positions.knee[0]).toBeGreaterThan(x);
  }
});

test("an explicit empty contact set releases the old desktop floor lock", () => {
  const contract = modelContract();
  // A bent rest chain keeps the desktop's historical target strictly reachable.
  contract.nodes[1].restOffset = [0.2, 0.9, 0]; contract.nodes[1].restPosition = [0.2, 0.9, 0];
  contract.nodes[2].restOffset = [-0.2, 0.9, 0]; contract.nodes[2].restPosition = [0, 1.8, 0];
  const model = new Rig2dModel(contract);
  expect(model.pose({ rootX: 0.1 }).positions.foot).toEqual([0, 1.8, 0]);
  expect(model.pose({ rootX: 0.1 }, {}).positions.foot[0]).toBeCloseTo(0.1, 10);
  expect(model.pose({ rootX: 0.1 }).positions.foot).toEqual([0, 1.8, 0]);
});

test("unreachable or unknown room contacts fail instead of stretching or reporting contact", () => {
  const model = new Rig2dModel(modelContract());
  expect(() => model.pose({}, { foot: [0, 3, 0] })).toThrow(/unreachable/i);
  expect(() => model.pose({}, { missing: [0, 1, 0] })).toThrow(/contact/i);
  expect(() => model.pose({}, { foot: [NaN, 1, 0] })).toThrow(/contact/i);
});

test("anchors follow their joint rotation instead of staying at a fixed rest point", () => {
  const model = new Rig2dModel(modelContract());
  const pose = model.pose({ turn: 90 }, {});
  const anchor = model.anchorPosition("foot", [0, 0.25, 0], pose);
  expect(anchor[0]).toBeCloseTo(-2.25, 10);
  expect(anchor[1]).toBeCloseTo(0, 10);
  expect(anchor[2]).toBe(0);
  expect(() => model.anchorPosition("missing", [0, 0, 0], pose)).toThrow(/anchor/i);
});

test("room projection includes posed depth without changing desktop deformation", () => {
  const contract = modelContract();
  contract.nodes[0].restOffset[2] = 2;
  contract.nodes.forEach((node) => { node.restPosition[2] = 2; });
  const model = new Rig2dModel(contract);
  const mesh: Rig2dMeshData = { id: "foot", positions: [[100, 102]], uvs: [[0, 0]], indices: [], drawOrder: 1, texture: "body.png", mask: "", isClippingMask: false, clipping: null };
  const pose = model.pose({}, {});
  expect(model.deform(mesh, pose)).toEqual([[100, 102]]);
  expect(model.deform(mesh, pose, 105 / 240)).toEqual([[100, 102.875]]);
  expect(model.deform(mesh, pose)).toEqual([[100, 102]]);
});

test("contact release blends endpoints while preserving both bone lengths", () => {
  const contract = modelContract();
  contract.nodes[1].restOffset = [0.2, 0.9, 0]; contract.nodes[1].restPosition = [0.2, 0.9, 0];
  contract.nodes[2].restOffset = [-0.2, 0.9, 0]; contract.nodes[2].restPosition = [0, 1.8, 0];
  contract.parameters.release = { min: 0, max: 1, initial: 0, frequency: 12 };
  contract.ik[0].release = "release";
  const model = new Rig2dModel(contract), values = { rootX: 0.1, turn: 8 };
  const forward = model.pose(values, {}).positions.foot;
  let previous: number[] | undefined;
  for (let i = 0; i <= 40; i++) {
    const release = (1 - Math.cos(i * Math.PI / 20)) / 2;
    const pose = model.pose({ ...values, release });
    const target = [0, 1.8, 0].map((v, axis) => v + (forward[axis] - v) * release);
    expect(pose.positions.foot).toEqual(target);
    for (const [a, b] of [["hip", "knee"], ["knee", "foot"]]) {
      expect(Math.hypot(...pose.positions[a].map((v, axis) => v - pose.positions[b][axis]))).toBeCloseTo(Math.hypot(0.2, 0.9), 10);
    }
    if (previous) expect(Math.hypot(...pose.positions.foot.map((v, axis) => v - previous![axis]))).toBeLessThan(0.02);
    previous = pose.positions.foot;
  }
  // Explicit scene contacts have priority over an authored release channel.
  expect(model.pose({ ...values, release: 1 }, { foot: [0, 1.8, 0] }).positions.foot).toEqual([0, 1.8, 0]);
});

test("contact release configuration fails closed outside a grounded 0-to-1 channel", () => {
  const contract = modelContract();
  contract.ik[0].release = "missing";
  expect(() => new Rig2dModel(contract)).toThrow(/parameter/i);
  contract.ik[0].release = "turn";
  expect(() => new Rig2dModel(contract)).toThrow(/contact release/i);
});

test("grounding lowers the root instead of stretching a nearly extended planted leg", () => {
  const contract = modelContract();
  contract.nodes[1].restOffset = [0.2, 0.9, 0]; contract.nodes[1].restPosition = [0.2, 0.9, 0];
  contract.nodes[2].restOffset = [-0.2, 0.9, 0]; contract.nodes[2].restPosition = [0, 1.8, 0];
  contract.grounding = { maxDrop: 0.2, reachMargin: 0.01 };
  const model = new Rig2dModel(contract), pose = model.pose({ rootX: 0.5 });
  expect(pose.groundingDrop).toBeGreaterThan(0);
  expect(pose.positions.foot).toEqual([0, 1.8, 0]);
  expect(pose.positions.hip[0]).toBe(0.5);
  for (const [a, b] of [["hip", "knee"], ["knee", "foot"]]) {
    expect(Math.hypot(...pose.positions[a].map((v, axis) => v - pose.positions[b][axis]))).toBeCloseTo(Math.hypot(0.2, 0.9), 10);
  }
  expect(model.pose({ rootX: 0.5 }, {}).groundingDrop).toBe(0);
  contract.parameters.release = { min: 0, max: 1, initial: 0, frequency: 12 };
  contract.ik[0].release = "release";
  const released = new Rig2dModel(contract);
  expect(released.pose({ rootX: 0.5, turn: 8, release: 1 }).positions.hip)
    .toEqual(released.pose({ rootX: 0.5, turn: 8, release: 0.999999 }).positions.hip);
  contract.grounding.maxDrop = 0.001;
  expect(() => new Rig2dModel(contract).pose({ rootX: 0.5 })).toThrow(/correction exceeds/i);
});
