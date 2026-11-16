import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/examples/jsm/postprocessing/OutputPass.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import type { ActivityNode } from './api';

type State = 'idle' | 'thinking' | 'learning' | 'speaking';
type HologramProps = {
  state: State;
  knowledgeCount?: number;
  activity: ActivityNode[];
  selectedNodeId: ActivityNode['id'];
  onNodeSelect: (id: ActivityNode['id']) => void;
  resourceMode?: 'normal' | 'gaming' | 'conserve';
};

type NodeId = ActivityNode['id'];
type SceneNode = { id: NodeId; group: THREE.Group; core: THREE.Mesh; halo: THREE.Sprite; ring: THREE.Mesh };
type Pathway = { from: NodeId; to: NodeId; curve: THREE.CatmullRomCurve3; tube: THREE.Mesh; pulses: THREE.Mesh[] };

const nodePositions: Record<NodeId, THREE.Vector3> = {
  input: new THREE.Vector3(-2.05, 0.35, 0.2),
  memory: new THREE.Vector3(-0.35, -1.72, 0.35),
  model: new THREE.Vector3(2.02, 0.3, 0.05),
  response: new THREE.Vector3(0.25, 1.78, -0.25),
};
const nodeNames: Record<NodeId, string> = { input: 'INPUT', memory: 'MEMORY / CONTEXT', model: 'MODEL TEAM', response: 'OUTPUT' };
const nodeColors: Record<ActivityNode['status'], number> = {
  idle: 0x47788a,
  active: 0x72efff,
  complete: 0x55d6a6,
  warning: 0xff9d72,
};
const nodeOrder: NodeId[] = ['input', 'memory', 'model', 'response'];

function createLabel(id: NodeId): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 96;
  const context = canvas.getContext('2d');
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = 'rgba(2, 13, 24, 0.86)';
    context.strokeStyle = 'rgba(91, 225, 247, 0.78)';
    context.lineWidth = 2;
    context.beginPath();
    context.roundRect(2, 2, 508, 92, 13);
    context.fill();
    context.stroke();
    context.font = '600 29px Consolas, monospace';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillStyle = '#c9f7ff';
    context.fillText(nodeNames[id], 256, 48);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, toneMapped: false }));
  sprite.scale.set(1.15, 0.215, 1);
  sprite.position.set(0.78, 0.04, 0);
  return sprite;
}

function makeGlowTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    const gradient = ctx.createRadialGradient(64, 64, 1, 64, 64, 64);
    gradient.addColorStop(0, 'rgba(123,245,255,0.9)');
    gradient.addColorStop(0.18, 'rgba(62,207,239,0.36)');
    gradient.addColorStop(0.55, 'rgba(22,126,176,0.12)');
    gradient.addColorStop(1, 'rgba(5,28,53,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);
  }
  return new THREE.CanvasTexture(canvas);
}

function makeDeterministicDust(count: number): Float32Array {
  const values = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    const a = i * 2.399963229728653;
    const y = 1 - ((i + 0.5) / count) * 2;
    const radius = 3.2 + ((i * 37) % 100) / 100 * 3.8;
    const ring = Math.sqrt(Math.max(0, 1 - y * y));
    values[i * 3] = Math.cos(a) * ring * radius;
    values[i * 3 + 1] = y * radius;
    values[i * 3 + 2] = Math.sin(a) * ring * radius;
  }
  return values;
}

export default function Hologram({ state, knowledgeCount = 0, activity, selectedNodeId, onNodeSelect, resourceMode = 'normal' }: HologramProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const livePropsRef = useRef({ state, knowledgeCount, activity, selectedNodeId, onNodeSelect, resourceMode });
  const [hoveredNode, setHoveredNode] = useState<NodeId | null>(null);
  livePropsRef.current = { state, knowledgeCount, activity, selectedNodeId, onNodeSelect, resourceMode };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    let renderer: THREE.WebGLRenderer;
    let composer: EffectComposer | null = null;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance', stencil: false, depth: true });
    } catch {
      const fallback = document.createElement('div');
      fallback.className = 'hologram-fallback';
      fallback.textContent = '3D CORE UNAVAILABLE · WEBGL INITIALIZATION FAILED';
      container.appendChild(fallback);
      return () => fallback.remove();
    }

    const reducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, resourceMode === 'gaming' ? 0.9 : resourceMode === 'conserve' ? 0.75 : 1.35));
    renderer.setClearColor(0x020710, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.22;
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.setAttribute('aria-label', 'Interactive three-dimensional JARVIS intelligence network. Drag to orbit, scroll to zoom, select a node to focus.');
    renderer.domElement.setAttribute('role', 'img');
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x030a14, 0.035);
    // A small procedural studio environment gives physical materials real
    // environment reflections without downloading HDR assets or using the network.
    const pmrem = new THREE.PMREMGenerator(renderer);
    const roomEnvironment = new RoomEnvironment();
    const environmentTexture = pmrem.fromScene(roomEnvironment, 0.04).texture;
    scene.environment = environmentTexture;
    roomEnvironment.dispose();
    pmrem.dispose();
    const camera = new THREE.PerspectiveCamera(39, 1, 0.1, 100);
    camera.position.set(0, 0, 7.1);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.enableZoom = true;
    controls.minDistance = 2.6;
    controls.maxDistance = 13;
    controls.rotateSpeed = 0.58;
    controls.zoomSpeed = 0.78;
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;

    scene.add(new THREE.AmbientLight(0x9bd9ea, 0.48));
    const keyLight = new THREE.PointLight(0x5be9ff, 24, 16, 2);
    keyLight.position.set(2.8, 3.4, 4.5);
    scene.add(keyLight);
    const rimLight = new THREE.PointLight(0x175eaa, 18, 14, 2);
    rimLight.position.set(-4, -2, -2.8);
    scene.add(rimLight);
    const amberLight = new THREE.PointLight(0xe99052, 5.5, 9, 2);
    amberLight.position.set(1.5, -3.5, 0.5);
    scene.add(amberLight);

    // Deep-space dust is ambient presentation only. Operational pulses below are driven by backend activity states.
    const dustGeometry = new THREE.BufferGeometry();
    const dustPositions = makeDeterministicDust(reducedMotion ? 220 : 420);
    dustGeometry.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));
    const dust = new THREE.Points(dustGeometry, new THREE.PointsMaterial({ color: 0x78cfe5, size: 0.025, transparent: true, opacity: 0.36, sizeAttenuation: true, depthWrite: false }));
    scene.add(dust);

    // Fine neural constellation around the core. Fixed topology; no synthetic activity/status is generated here.
    const latticePositions = new Float32Array(120 * 3);
    for (let index = 0; index < 120; index += 1) {
      const angle = (index / 120) * Math.PI * 2;
      const radius = 2.42 + Math.sin(index * 1.71) * 0.24;
      latticePositions[index * 3] = Math.cos(angle) * radius;
      latticePositions[index * 3 + 1] = Math.sin(angle * 2.7) * 0.82;
      latticePositions[index * 3 + 2] = Math.sin(angle) * radius * 0.35;
    }
    const latticeGeometry = new THREE.BufferGeometry();
    latticeGeometry.setAttribute('position', new THREE.BufferAttribute(latticePositions, 3));
    const lattice = new THREE.Points(latticeGeometry, new THREE.PointsMaterial({ color: 0x3ca8cc, size: 0.024, transparent: true, opacity: 0.3, depthWrite: false }));
    scene.add(lattice);

    const coreGroup = new THREE.Group();
    scene.add(coreGroup);
    const outerShellMaterial = new THREE.MeshBasicMaterial({ color: 0x22c8ee, wireframe: true, transparent: true, opacity: 0.62, depthWrite: false });
    const outerShell = new THREE.Mesh(new THREE.IcosahedronGeometry(0.94, 3), outerShellMaterial);
    coreGroup.add(outerShell);
    const innerShell = new THREE.Mesh(new THREE.IcosahedronGeometry(0.68, 2), new THREE.MeshBasicMaterial({ color: 0x0a5d86, wireframe: true, transparent: true, opacity: 0.26, depthWrite: false }));
    coreGroup.add(innerShell);
    const coreSphere = new THREE.Mesh(
      new THREE.SphereGeometry(0.39, 48, 48),
      new THREE.MeshPhysicalMaterial({ color: 0xb4f7ff, emissive: 0x22c8ee, emissiveIntensity: 2.2, roughness: 0.13, metalness: 0.42, transmission: 0.22, transparent: true, opacity: 0.88, clearcoat: 1, clearcoatRoughness: 0.1 }),
    );
    coreGroup.add(coreSphere);
    const coreGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeGlowTexture(), color: 0x42dff7, transparent: true, opacity: 0.68, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    coreGlow.scale.set(2.2, 2.2, 1);
    coreGroup.add(coreGlow);

    const orbitalRings: THREE.Mesh[] = [];
    [1.34, 1.58, 1.84, 2.08].forEach((radius, index) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius, index === 0 ? 0.012 : 0.006, 8, 180),
        new THREE.MeshBasicMaterial({ color: index === 3 ? 0xe99052 : index % 2 ? 0x1b86b7 : 0x39dcf2, transparent: true, opacity: 0.54 - index * 0.075, depthWrite: false }),
      );
      ring.rotation.set(Math.PI / (2.15 + index * 0.27), index * 0.42, index * 0.31);
      ring.userData.baseRotation = ring.rotation.clone();
      coreGroup.add(ring);
      orbitalRings.push(ring);
    });
    // Small segmented orbit markers add depth without requiring a large mesh count.
    const markerGeometry = new THREE.SphereGeometry(0.026, 10, 10);
    const markerMaterial = new THREE.MeshBasicMaterial({ color: 0x90f3ff, transparent: true, opacity: 0.82 });
    const orbitMarkers = new THREE.InstancedMesh(markerGeometry, markerMaterial, 48);
    const markerDummy = new THREE.Object3D();
    for (let i = 0; i < 48; i += 1) {
      const angle = (i / 48) * Math.PI * 2;
      const radius = i % 3 === 0 ? 1.86 : 1.58;
      markerDummy.position.set(Math.cos(angle) * radius, Math.sin(angle * 2) * 0.2, Math.sin(angle) * radius);
      markerDummy.scale.setScalar(i % 6 === 0 ? 1.7 : 0.75);
      markerDummy.updateMatrix();
      orbitMarkers.setMatrixAt(i, markerDummy.matrix);
    }
    coreGroup.add(orbitMarkers);

    // Exactly one small instance per persisted memory, capped for rendering efficiency.
    const memoryCapacity = 180;
    const memoryMesh = new THREE.InstancedMesh(
      new THREE.SphereGeometry(1, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x22c8ee, transparent: true, opacity: 0.8 }),
      memoryCapacity,
    );
    const memoryDummy = new THREE.Object3D();
    for (let index = 0; index < memoryCapacity; index += 1) {
      const angle = (index / memoryCapacity) * Math.PI * 2;
      const radius = 1.12 + (index % 5) * 0.075;
      memoryDummy.position.set(Math.cos(angle) * radius, Math.sin(angle * 2.8) * 0.31, Math.sin(angle) * radius);
      memoryDummy.scale.setScalar(index % 9 === 0 ? 0.028 : 0.014);
      memoryDummy.updateMatrix();
      memoryMesh.setMatrixAt(index, memoryDummy.matrix);
      memoryMesh.setColorAt(index, new THREE.Color(index % 11 === 0 ? 0xffb16e : 0x37d5ef));
    }
    memoryMesh.count = 0;
    memoryMesh.instanceMatrix.needsUpdate = true;
    if (memoryMesh.instanceColor) memoryMesh.instanceColor.needsUpdate = true;
    coreGroup.add(memoryMesh);

    const sceneNodes: SceneNode[] = nodeOrder.map((id, index) => {
      const group = new THREE.Group();
      group.position.copy(nodePositions[id]);
      group.userData.activityId = id;
      const coreMaterial = new THREE.MeshPhysicalMaterial({
        color: 0x7defff,
        emissive: 0x1e90ae,
        emissiveIntensity: 0.85,
        metalness: 0.35,
        roughness: 0.2,
        transparent: true,
        opacity: 0.93,
        clearcoat: 1,
      });
      const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.115 + (index === 2 ? 0.012 : 0), 2), coreMaterial);
      core.userData.activityId = id;
      group.add(core);
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.18, 0.006, 8, 56),
        new THREE.MeshBasicMaterial({ color: 0x55dff4, transparent: true, opacity: 0.64, depthWrite: false }),
      );
      ring.userData.activityId = id;
      ring.rotation.x = Math.PI / 2.8;
      group.add(ring);
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: makeGlowTexture(), color: 0x38d9f2, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
      halo.scale.set(0.78, 0.78, 1);
      group.add(halo);
      group.add(createLabel(id));
      scene.add(group);
      return { id, group, core, halo, ring };
    });

    const pathPairs: Array<[NodeId, NodeId]> = [['input', 'memory'], ['memory', 'model'], ['model', 'response']];
    const pathways: Pathway[] = pathPairs.map(([from, to], index) => {
      const start = nodePositions[from].clone();
      const end = nodePositions[to].clone();
      const mid = start.clone().lerp(end, 0.5);
      mid.z += index % 2 === 0 ? 0.42 : -0.38;
      mid.y += index === 1 ? -0.25 : 0.12;
      const curve = new THREE.CatmullRomCurve3([start, mid, end]);
      const tube = new THREE.Mesh(
        new THREE.TubeGeometry(curve, 52, 0.008, 6, false),
        new THREE.MeshBasicMaterial({ color: 0x2b839e, transparent: true, opacity: 0.22, depthWrite: false }),
      );
      tube.userData.connection = `${from}:${to}`;
      scene.add(tube);
      const pulses = Array.from({ length: 2 }, (_, pulseIndex) => {
        const pulse = new THREE.Mesh(
          new THREE.SphereGeometry(pulseIndex === 0 ? 0.032 : 0.022, 12, 12),
          new THREE.MeshBasicMaterial({ color: 0x90f8ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }),
        );
        scene.add(pulse);
        return pulse;
      });
      return { from, to, curve, tube, pulses };
    });
    const inboundCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(-3.35, 0.62, 0.4),
      new THREE.Vector3(-2.65, 0.55, 0.2),
      nodePositions.input.clone(),
    ]);
    const inboundPulse = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 12), new THREE.MeshBasicMaterial({ color: 0x7af3ff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    scene.add(inboundPulse);
    const outboundCurve = new THREE.CatmullRomCurve3([
      nodePositions.response.clone(),
      new THREE.Vector3(0.15, 2.35, -0.3),
      new THREE.Vector3(0.15, 3.02, -0.5),
    ]);
    const outboundPulse = new THREE.Mesh(new THREE.SphereGeometry(0.035, 12, 12), new THREE.MeshBasicMaterial({ color: 0x9aeaff, transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
    scene.add(outboundPulse);

    // Post-processing bloom is part of the actual WebGL render pipeline, not a CSS glow imitation.
    try {
      composer = new EffectComposer(renderer);
      composer.addPass(new RenderPass(scene, camera));
      composer.addPass(new UnrealBloomPass(new THREE.Vector2(1, 1), reducedMotion ? 0.7 : 1.05, 0.58, 0.14));
      composer.addPass(new OutputPass());
    } catch {
      composer = null;
    }

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const findActivityGroup = (event: PointerEvent | MouseEvent): SceneNode | null => {
      const bounds = renderer.domElement.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return null;
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(sceneNodes.map(item => item.group), true)[0]?.object;
      if (!hit) return null;
      let ancestor: THREE.Object3D | null = hit;
      while (ancestor && !ancestor.userData.activityId) ancestor = ancestor.parent;
      const id = ancestor?.userData.activityId as NodeId | undefined;
      return id ? sceneNodes.find(item => item.id === id) ?? null : null;
    };

    let focusAnimation: { fromPosition: THREE.Vector3; toPosition: THREE.Vector3; fromTarget: THREE.Vector3; toTarget: THREE.Vector3; started: number; duration: number } | null = null;
    const beginFocus = (id?: NodeId) => {
      const target = id ? nodePositions[id].clone() : new THREE.Vector3(0, 0, 0);
      const direction = new THREE.Vector3().subVectors(camera.position, controls.target).normalize();
      if (direction.lengthSq() < 0.001) direction.set(0, 0, 1);
      const distance = id ? 3.3 : 7.1;
      focusAnimation = {
        fromPosition: camera.position.clone(),
        toPosition: target.clone().add(direction.multiplyScalar(distance)),
        fromTarget: controls.target.clone(),
        toTarget: target,
        started: clock.elapsedTime,
        duration: reducedMotion ? 0.01 : 0.85,
      };
    };
    const onResetView = () => beginFocus();
    let pointerStart: { x: number; y: number } | null = null;
    let pointerDragged = false;
    const onPointerDown = (event: PointerEvent) => {
      pointerStart = { x: event.clientX, y: event.clientY };
      pointerDragged = false;
    };
    const onClick = (event: MouseEvent) => {
      if (pointerDragged) return;
      const target = findActivityGroup(event);
      if (target) {
        livePropsRef.current.onNodeSelect(target.id);
        beginFocus(target.id);
      }
    };
    const onPointerMove = (event: PointerEvent) => {
      if (pointerStart && Math.hypot(event.clientX - pointerStart.x, event.clientY - pointerStart.y) > 6) {
        pointerDragged = true;
      }
      const target = findActivityGroup(event);
      const next = target?.id ?? null;
      renderer.domElement.style.cursor = target ? 'pointer' : 'grab';
      if (next !== hoveredNodeRef.current) {
        hoveredNodeRef.current = next;
        setHoveredNode(next);
      }
    };
    const onPointerLeave = () => {
      renderer.domElement.style.cursor = 'grab';
      hoveredNodeRef.current = null;
      setHoveredNode(null);
    };
    renderer.domElement.style.cursor = 'grab';
    renderer.domElement.addEventListener('pointerdown', onPointerDown);
    renderer.domElement.addEventListener('click', onClick);
    renderer.domElement.addEventListener('jarvis-reset-view', onResetView);
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);
    const onControlStart = () => { focusAnimation = null; };
    controls.addEventListener('start', onControlStart);

    const clock = new THREE.Clock();
    const hoveredNodeRef = { current: null as NodeId | null };
    let animationFrame = 0;
    let lastFrameAt = 0;
    let appliedQuality: HologramProps['resourceMode'] | null = null;
    const resize = () => {
      const width = Math.max(1, container.clientWidth);
      const height = Math.max(1, container.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      composer?.setSize(width, height);
    };
    const renderFrame = (now: number) => {
      animationFrame = window.requestAnimationFrame(renderFrame);
      if (document.visibilityState === 'hidden') return;
      const current = livePropsRef.current;
      const targetFrameMs = current.resourceMode === 'gaming' ? 1000 / 30 : current.resourceMode === 'conserve' ? 1000 / 24 : current.state === 'idle' ? 1000 / 40 : 1000 / 55;
      if (now - lastFrameAt < targetFrameMs) return;
      lastFrameAt = now;
      if (appliedQuality !== current.resourceMode) {
        const ratioCap = current.resourceMode === 'gaming' ? 0.9 : current.resourceMode === 'conserve' ? 0.75 : 1.35;
        renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, ratioCap));
        composer?.setPixelRatio(Math.min(window.devicePixelRatio || 1, ratioCap));
        appliedQuality = current.resourceMode;
        resize();
      }
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;

      const pulse = current.state === 'thinking' ? 1.13 : current.state === 'learning' ? 1.2 : current.state === 'speaking' ? 1.1 : 1;
      const breathing = reducedMotion ? 0 : Math.sin(elapsed * (current.state === 'speaking' ? 4.4 : 1.25)) * (current.state === 'idle' ? 0.012 : 0.045);
      const growth = 1 + Math.min(Math.log2(Math.max(0, current.knowledgeCount) + 1) * 0.018, 0.12);
      coreGroup.rotation.y += delta * (reducedMotion ? 0.015 : current.state === 'thinking' ? 0.36 : 0.12);
      coreGroup.rotation.x = reducedMotion ? 0 : Math.sin(elapsed * 0.2) * 0.1;
      coreGroup.scale.setScalar(growth);
      outerShell.scale.setScalar(pulse + breathing);
      innerShell.rotation.y -= delta * (reducedMotion ? 0.008 : 0.19);
      coreSphere.scale.setScalar(1 + breathing * 0.55);
      outerShellMaterial.color.setHex(current.state === 'learning' ? 0xffa467 : current.state === 'thinking' ? 0x5de7ff : current.state === 'speaking' ? 0x9bceff : 0x22c8ee);
      memoryMesh.count = Math.min(memoryCapacity, Math.max(0, Math.floor(current.knowledgeCount)));
      memoryMesh.instanceMatrix.needsUpdate = true;
      orbitalRings.forEach((ring, index) => {
        if (!reducedMotion) {
          ring.rotation.y += delta * (index % 2 ? -0.055 : 0.04);
          ring.rotation.x += delta * (index % 2 ? 0.018 : -0.014);
        }
      });
      if (!reducedMotion) {
        dust.rotation.y += delta * 0.006;
        lattice.rotation.y -= delta * 0.012;
      }

      const byId = new Map<NodeId, ActivityNode>(current.activity.map(node => [node.id, node] as const));
      const selected = current.selectedNodeId;
      sceneNodes.forEach((node, index) => {
        const data = byId.get(node.id);
        const isSelected = selected === node.id;
        const isHovered = hoveredNodeRef.current === node.id;
        const active = data?.status === 'active';
        const warning = data?.status === 'warning';
        const targetScale = (isSelected ? 1.22 : 1) * (isHovered ? 1.18 : 1) * (active ? 1 + Math.sin(elapsed * 5.4 + index) * 0.12 : 1);
        node.group.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 1 - Math.exp(-delta * 9));
        node.group.position.y = nodePositions[node.id].y + (reducedMotion ? 0 : Math.sin(elapsed * 0.72 + index * 1.6) * 0.035);
        const color = warning ? nodeColors.warning : data?.status === 'complete' ? nodeColors.complete : active ? nodeColors.active : isSelected || isHovered ? 0xa8f5ff : nodeColors.idle;
        const material = node.core.material as THREE.MeshPhysicalMaterial;
        material.color.setHex(color);
        material.emissive.setHex(color);
        material.emissiveIntensity = active ? 1.8 + Math.sin(elapsed * 6) * 0.45 : isSelected || isHovered ? 1.25 : 0.5;
        material.opacity = data?.status === 'idle' ? 0.72 : 1;
        node.ring.material && ((node.ring.material as THREE.MeshBasicMaterial).color.setHex(color));
        (node.ring.material as THREE.MeshBasicMaterial).opacity = active ? 0.95 : isSelected || isHovered ? 0.88 : 0.38;
        node.ring.rotation.z += delta * (active && !reducedMotion ? 0.55 : reducedMotion ? 0 : 0.12);
        node.halo.material.color.setHex(color);
        node.halo.material.opacity = active ? 0.88 : isSelected || isHovered ? 0.72 : 0.3;
      });

      pathways.forEach((pathway, index) => {
        const fromNode = byId.get(pathway.from);
        const toNode = byId.get(pathway.to);
        const targetActive = toNode?.status === 'active';
        const sourceWarning = fromNode?.status === 'warning' || toNode?.status === 'warning';
        const isSelectedPath = selected === pathway.from || selected === pathway.to;
        const material = pathway.tube.material as THREE.MeshBasicMaterial;
        material.color.setHex(sourceWarning ? nodeColors.warning : targetActive ? 0x7ef5ff : 0x2b839e);
        material.opacity = targetActive ? 0.82 : isSelectedPath ? 0.46 : 0.16;
        pathway.pulses.forEach((particle, pulseIndex) => {
          const visible = targetActive;
          const particleMaterial = particle.material as THREE.MeshBasicMaterial;
          particleMaterial.opacity = visible ? 0.95 : 0;
          if (visible) {
            const travel = (elapsed * (reducedMotion ? 0.16 : 0.34) + pulseIndex * 0.48 + index * 0.23) % 1;
            particle.position.copy(pathway.curve.getPoint(travel));
          }
        });
      });
      const inputActive = byId.get('input')?.status === 'active';
      (inboundPulse.material as THREE.MeshBasicMaterial).opacity = inputActive ? 0.95 : 0;
      if (inputActive) inboundPulse.position.copy(inboundCurve.getPoint((elapsed * (reducedMotion ? 0.12 : 0.32)) % 1));
      const outputActive = byId.get('response')?.status === 'active';
      (outboundPulse.material as THREE.MeshBasicMaterial).opacity = outputActive ? 0.95 : 0;
      if (outputActive) outboundPulse.position.copy(outboundCurve.getPoint((elapsed * (reducedMotion ? 0.12 : 0.29)) % 1));

      if (focusAnimation) {
        const progress = Math.min(1, (elapsed - focusAnimation.started) / focusAnimation.duration);
        const eased = progress * progress * (3 - 2 * progress);
        camera.position.lerpVectors(focusAnimation.fromPosition, focusAnimation.toPosition, eased);
        controls.target.lerpVectors(focusAnimation.fromTarget, focusAnimation.toTarget, eased);
        if (progress >= 1) focusAnimation = null;
      }
      controls.update();
      if (composer) composer.render(delta);
      else renderer.render(scene, camera);
    };

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    renderFrame(0);

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      controls.removeEventListener('start', onControlStart);
      controls.dispose();
      renderer.domElement.removeEventListener('click', onClick);
      renderer.domElement.removeEventListener('jarvis-reset-view', onResetView);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
      composer?.dispose();
      environmentTexture.dispose();
      const disposedGeometries = new Set<THREE.BufferGeometry>();
      const disposedMaterials = new Set<THREE.Material>();
      scene.traverse(object => {
        const renderable = object as THREE.Mesh;
        if (renderable.geometry && !disposedGeometries.has(renderable.geometry)) {
          disposedGeometries.add(renderable.geometry);
          renderable.geometry.dispose();
        }
        const materials = Array.isArray(renderable.material) ? renderable.material : renderable.material ? [renderable.material] : [];
        materials.forEach(material => {
          if (disposedMaterials.has(material)) return;
          disposedMaterials.add(material);
          const texture = (material as THREE.SpriteMaterial).map;
          texture?.dispose();
          material.dispose();
        });
      });
      renderer.dispose();
      renderer.forceContextLoss();
      if (renderer.domElement.parentElement === container) container.removeChild(renderer.domElement);
    };
  }, []);

  const resetView = () => {
    const canvas = containerRef.current?.querySelector('canvas');
    if (!canvas) return;
    canvas.dispatchEvent(new CustomEvent('jarvis-reset-view'));
  };

  return (
    <div className="hologram-scene-shell">
      <div className="hologram-canvas" ref={containerRef} />
      <div className="hologram-scene-toolbar">
        <span className="hologram-scene-label">3D NEURAL FIELD <i /> LIVE EVENT FEED</span>
        <button type="button" onClick={resetView} title="Reset camera to the full intelligence core">RESET VIEW</button>
      </div>
      {hoveredNode && <div className="hologram-hover-readout">{nodeNames[hoveredNode]} <span>· SELECT TO FOCUS</span></div>}
      <div className="hologram-controls-hint">DRAG TO ORBIT · SCROLL TO ZOOM · SELECT A NODE</div>
    </div>
  );
}
