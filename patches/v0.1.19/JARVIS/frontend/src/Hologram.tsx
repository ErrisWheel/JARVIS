import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ActivityNode } from './api';

type State = 'idle' | 'thinking' | 'learning' | 'speaking';
type HologramProps = {
  state: State;
  knowledgeCount?: number;
  activity: ActivityNode[];
  selectedNodeId: ActivityNode['id'];
  onNodeSelect: (id: ActivityNode['id']) => void;
};

const nodePositions: Record<ActivityNode['id'], [number, number, number]> = {
  input: [-1.85, 0.36, 0.15],
  memory: [-0.25, -1.68, 0.3],
  model: [1.83, 0.32, 0.05],
  response: [0.12, 1.72, -0.22],
};
const nodeColors: Record<ActivityNode['status'], number> = {
  idle: 0x47788a,
  active: 0x72efff,
  complete: 0x55d6a6,
  warning: 0xff9d72,
};

function makeLabelSprite(id: ActivityNode['id']): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const context = canvas.getContext('2d');
  if (context) {
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = 'rgba(4, 13, 22, 0.78)';
    context.strokeStyle = 'rgba(91, 225, 247, 0.72)';
    context.lineWidth = 3;
    context.beginPath();
    context.roundRect(2, 2, 252, 60, 10);
    context.fill();
    context.stroke();
    context.font = 'bold 27px Consolas, monospace';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillStyle = '#bfeefa';
    context.fillText(id === 'memory' ? 'CONTEXT' : id === 'response' ? 'ANSWER' : id.toUpperCase(), 128, 32);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.86, 0.215, 1);
  sprite.position.set(0.58, 0.035, 0);
  return sprite;
}

export default function Hologram({ state, knowledgeCount = 0, activity, selectedNodeId, onNodeSelect }: HologramProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const livePropsRef = useRef({ state, knowledgeCount, activity, selectedNodeId, onNodeSelect });
  livePropsRef.current = { state, knowledgeCount, activity, selectedNodeId, onNodeSelect };

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    } catch {
      const fallback = document.createElement('div');
      fallback.className = 'hologram-fallback';
      fallback.textContent = '3D CORE UNAVAILABLE · WEBGL INITIALIZATION FAILED';
      container.appendChild(fallback);
      return () => fallback.remove();
    }

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.6));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.domElement.style.display = 'block';
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.setAttribute('aria-label', 'Interactive three-dimensional JARVIS hologram');
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(0, 0, 6.4);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enablePan = false;
    controls.minDistance = 4;
    controls.maxDistance = 10;
    controls.rotateSpeed = 0.7;
    controls.enableDamping = true;
    controls.dampingFactor = 0.055;

    scene.add(new THREE.AmbientLight(0x9bd9ea, 0.65));
    const pointLight = new THREE.PointLight(0x5be9ff, 1.4);
    pointLight.position.set(3, 3, 4);
    scene.add(pointLight);

    const starPositions = new Float32Array(850 * 3);
    for (let index = 0; index < 850; index += 1) {
      const radius = 13 + Math.random() * 18;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      starPositions[index * 3] = radius * Math.sin(phi) * Math.cos(theta);
      starPositions[index * 3 + 1] = radius * Math.cos(phi);
      starPositions[index * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    }
    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(starGeometry, new THREE.PointsMaterial({ color: 0x83c3d4, size: 0.035, transparent: true, opacity: 0.62, sizeAttenuation: true, depthWrite: false }));
    scene.add(stars);

    const coreGroup = new THREE.Group();
    scene.add(coreGroup);
    const shellMaterial = new THREE.MeshBasicMaterial({ color: 0x22c8ee, wireframe: true, transparent: true, opacity: 0.72 });
    const shell = new THREE.Mesh(new THREE.IcosahedronGeometry(1.05, 2), shellMaterial);
    coreGroup.add(shell);
    coreGroup.add(new THREE.Mesh(new THREE.IcosahedronGeometry(0.76, 3), new THREE.MeshBasicMaterial({ color: 0x0a5d86, wireframe: true, transparent: true, opacity: 0.28 })));
    coreGroup.add(new THREE.Mesh(
      new THREE.SphereGeometry(0.48, 48, 48),
      new THREE.MeshPhysicalMaterial({ color: 0xb4f7ff, emissive: 0x22c8ee, emissiveIntensity: 1.65, roughness: 0.16, metalness: 0.4, transmission: 0.25, transparent: true, opacity: 0.82 }),
    ));
    [1.55, 1.82, 2.08].forEach((radius, index) => {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius, index === 0 ? 0.009 : 0.005, 8, 160),
        new THREE.MeshBasicMaterial({ color: index === 2 ? 0xf28b4a : 0x22c8ee, transparent: true, opacity: 0.68 - index * 0.12 }),
      );
      ring.rotation.set(Math.PI / (2 + index), index * 0.45, index * 0.25);
      coreGroup.add(ring);
    });

    const knowledgeGeometry = new THREE.SphereGeometry(1, 8, 8);
    const knowledgeMaterial = new THREE.MeshBasicMaterial({ color: 0x22c8ee });
    const knowledgeMesh = new THREE.InstancedMesh(knowledgeGeometry, knowledgeMaterial, 180);
    const dummy = new THREE.Object3D();
    for (let index = 0; index < 180; index += 1) {
      const angle = (index / 180) * Math.PI * 2;
      const radius = 1.28 + (index % 4) * 0.09;
      dummy.position.set(Math.cos(angle) * radius, Math.sin(angle * 3) * 0.35, Math.sin(angle) * radius);
      const pointScale = index % 6 === 0 ? 0.035 : 0.016;
      dummy.scale.setScalar(pointScale);
      dummy.updateMatrix();
      knowledgeMesh.setMatrixAt(index, dummy.matrix);
      knowledgeMesh.setColorAt(index, new THREE.Color(index % 7 === 0 ? 0xff9d55 : 0x22c8ee));
    }
    knowledgeMesh.count = 36;
    knowledgeMesh.instanceMatrix.needsUpdate = true;
    if (knowledgeMesh.instanceColor) knowledgeMesh.instanceColor.needsUpdate = true;
    coreGroup.add(knowledgeMesh);

    const activityMeshes: THREE.Mesh[] = [];
    const activityEntries = (Object.keys(nodePositions) as ActivityNode['id'][]).map(id => {
      const nodeMesh = new THREE.Mesh(
        new THREE.SphereGeometry(0.085, 18, 18),
        new THREE.MeshBasicMaterial({ color: nodeColors.idle, transparent: true, opacity: 0.58 }),
      );
      nodeMesh.position.set(...nodePositions[id]);
      nodeMesh.userData.activityId = id;
      const label = makeLabelSprite(id);
      nodeMesh.add(label);
      scene.add(nodeMesh);
      activityMeshes.push(nodeMesh);
      return { id, mesh: nodeMesh, label };
    });

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const findActivityMesh = (event: MouseEvent): THREE.Mesh | null => {
      const bounds = renderer.domElement.getBoundingClientRect();
      if (!bounds.width || !bounds.height) return null;
      pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
      pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      return (raycaster.intersectObjects(activityMeshes, false)[0]?.object as THREE.Mesh | undefined) ?? null;
    };
    const onClick = (event: MouseEvent) => {
      const target = findActivityMesh(event);
      const id = target?.userData.activityId as ActivityNode['id'] | undefined;
      if (id) livePropsRef.current.onNodeSelect(id);
    };
    const onPointerMove = (event: PointerEvent) => {
      renderer.domElement.style.cursor = findActivityMesh(event) ? 'pointer' : 'grab';
    };
    const onPointerLeave = () => { renderer.domElement.style.cursor = 'grab'; };
    renderer.domElement.style.cursor = 'grab';
    renderer.domElement.addEventListener('click', onClick);
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);

    let animationFrame = 0;
    const clock = new THREE.Clock();
    const renderFrame = () => {
      animationFrame = window.requestAnimationFrame(renderFrame);
      const delta = Math.min(clock.getDelta(), 0.05);
      const elapsed = clock.elapsedTime;
      const current = livePropsRef.current;
      const pulse = current.state === 'thinking' ? 1.12 : current.state === 'learning' ? 1.2 : current.state === 'speaking' ? 1.08 : 1;
      const growth = 1 + Math.min(Math.log2(Math.max(0, current.knowledgeCount) + 1) * 0.025, 0.18);
      coreGroup.rotation.y += delta * (current.state === 'thinking' ? 0.55 : 0.16);
      coreGroup.rotation.x = Math.sin(elapsed * 0.22) * 0.12;
      coreGroup.scale.setScalar(growth);
      shell.scale.setScalar(pulse + Math.sin(elapsed * (current.state === 'speaking' ? 5 : 1.4)) * (current.state === 'idle' ? 0.018 : 0.055));
      const coreColor = current.state === 'learning' ? 0xff9d55 : current.state === 'thinking' ? 0x5de7ff : current.state === 'speaking' ? 0x9bceff : 0x22c8ee;
      shellMaterial.color.setHex(coreColor);
      knowledgeMaterial.color.setHex(coreColor);
      knowledgeMesh.count = Math.min(36 + Math.max(0, Math.floor(current.knowledgeCount) * 2), 180);

      const byId = new Map<ActivityNode['id'], ActivityNode>();
      current.activity.forEach(node => byId.set(node.id, node));
      activityEntries.forEach(({ id, mesh }, index) => {
        const node = byId.get(id);
        const selected = current.selectedNodeId === id;
        const activePulse = node?.status === 'active' ? 1 + Math.sin(elapsed * 5 + index) * 0.2 : 1;
        mesh.scale.setScalar((selected ? 1.48 : 1) * activePulse);
        mesh.position.y = nodePositions[id][1] + Math.sin(elapsed * 0.9 + index * 1.7) * 0.045;
        const material = mesh.material as THREE.MeshBasicMaterial;
        material.color.setHex(selected ? 0xffffff : nodeColors[node?.status ?? 'idle']);
        material.opacity = node?.status === 'idle' ? 0.58 : 0.98;
      });
      controls.update();
      renderer.render(scene, camera);
    };

    const resize = () => {
      const width = Math.max(1, container.clientWidth);
      const height = Math.max(1, container.clientHeight);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();
    renderFrame();

    return () => {
      window.cancelAnimationFrame(animationFrame);
      observer.disconnect();
      controls.dispose();
      renderer.domElement.removeEventListener('click', onClick);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
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

  return <div className="hologram-canvas" ref={containerRef} />;
}
