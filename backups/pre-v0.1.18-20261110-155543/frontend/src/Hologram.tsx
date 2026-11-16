import { Canvas, useFrame } from '@react-three/fiber';
import { Html, OrbitControls, Stars } from '@react-three/drei';
import { useRef } from 'react';
import * as THREE from 'three';
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

function Core({ state, knowledgeCount }: { state: State; knowledgeCount: number }) {
  const group = useRef<THREE.Group>(null);
  const shell = useRef<THREE.Mesh>(null);
  const pulse = state === 'thinking' ? 1.12 : state === 'learning' ? 1.2 : state === 'speaking' ? 1.08 : 1;
  const growth = 1 + Math.min(Math.log2(Math.max(0, knowledgeCount) + 1) * 0.025, 0.18);
  const nodeCount = Math.min(36 + Math.max(0, Math.floor(knowledgeCount)) * 2, 180);
  useFrame(({ clock }, delta) => {
    if (!group.current || !shell.current) return;
    group.current.rotation.y += delta * (state === 'thinking' ? 0.55 : 0.16);
    group.current.scale.setScalar(growth);
    group.current.rotation.x = Math.sin(clock.elapsedTime * 0.22) * 0.12;
    const scale = pulse + Math.sin(clock.elapsedTime * (state === 'speaking' ? 5 : 1.4)) * (state === 'idle' ? 0.018 : 0.055);
    shell.current.scale.setScalar(scale);
  });
  const color = state === 'learning' ? '#ff9d55' : state === 'thinking' ? '#5de7ff' : state === 'speaking' ? '#9bceff' : '#22c8ee';
  return <group ref={group}>
    <mesh ref={shell}><icosahedronGeometry args={[1.05, 2]} /><meshBasicMaterial color={color} wireframe transparent opacity={0.72} /></mesh>
    <mesh><icosahedronGeometry args={[0.76, 3]} /><meshBasicMaterial color="#0a5d86" wireframe transparent opacity={0.28} /></mesh>
    <mesh><sphereGeometry args={[0.48, 48, 48]} /><meshPhysicalMaterial color="#b4f7ff" emissive={color} emissiveIntensity={1.65} roughness={0.16} metalness={0.4} transmission={0.25} transparent opacity={0.82} /></mesh>
    {[1.55, 1.82, 2.08].map((radius, i) => <mesh key={radius} rotation={[Math.PI / (2 + i), i * 0.45, i * 0.25]}>
      <torusGeometry args={[radius, i === 0 ? 0.009 : 0.005, 8, 160]} />
      <meshBasicMaterial color={i === 2 ? '#f28b4a' : color} transparent opacity={0.68 - i * 0.12} />
    </mesh>)}
    {Array.from({ length: nodeCount }, (_, i) => {
      const a = (i / nodeCount) * Math.PI * 2;
      const r = (1.28 + (i % 4) * 0.09) * (1 + Math.min(Math.log2(knowledgeCount + 1) * 0.035, 0.24));
      return <mesh key={i} position={[Math.cos(a) * r, Math.sin(a * 3) * 0.35, Math.sin(a) * r]}>
        <sphereGeometry args={[i % 6 === 0 ? 0.035 : 0.016, 8, 8]} /><meshBasicMaterial color={i % 7 === 0 ? '#ff9d55' : color} />
      </mesh>;
    })}
  </group>;
}

function ActivityPoint({
  node, index, selected, onSelect,
}: {
  node: ActivityNode; index: number; selected: boolean; onSelect: (id: ActivityNode['id']) => void;
}) {
  const mesh = useRef<THREE.Mesh>(null);
  const colors = { idle: '#47788a', active: '#72efff', complete: '#55d6a6', warning: '#ff9d72' };
  useFrame(({ clock }) => {
    if (!mesh.current) return;
    const pulse = node.status === 'active' ? 1 + Math.sin(clock.elapsedTime * 5 + index) * 0.2 : 1;
    mesh.current.scale.setScalar((selected ? 1.48 : 1) * pulse);
    mesh.current.position.y = nodePositions[node.id][1] + Math.sin(clock.elapsedTime * 0.9 + index * 1.7) * 0.045;
  });
  const color = selected ? '#ffffff' : colors[node.status];
  return <mesh
    ref={mesh}
    position={nodePositions[node.id]}
    onClick={event => { event.stopPropagation(); onSelect(node.id); }}
    onPointerOver={() => { document.body.style.cursor = 'pointer'; }}
    onPointerOut={() => { document.body.style.cursor = 'auto'; }}
  >
    <sphereGeometry args={[selected ? 0.105 : 0.085, 18, 18]} />
    <meshBasicMaterial color={color} transparent opacity={node.status === 'idle' ? 0.58 : 0.98} />
    <Html position={[0.18, 0.02, 0]} distanceFactor={9} occlude={false}>
      <div className={`holo-node-label ${node.status} ${selected ? 'selected' : ''}`}>{node.id === 'memory' ? 'CONTEXT' : node.id === 'response' ? 'ANSWER' : node.id.toUpperCase()}</div>
    </Html>
  </mesh>;
}

function ActivityGraph({ activity: nodes, selectedNodeId, onNodeSelect }: Pick<HologramProps, 'activity' | 'selectedNodeId' | 'onNodeSelect'>) {
  return <group>
    {nodes.map((node, index) => <ActivityPoint key={node.id} node={node} index={index} selected={selectedNodeId === node.id} onSelect={onNodeSelect} />)}
  </group>;
}

export default function Hologram({ state, knowledgeCount = 0, activity, selectedNodeId, onNodeSelect }: HologramProps) {
  return <div className="hologram-canvas">
    <Canvas camera={{ position: [0, 0, 6.4], fov: 42 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }}>
      <ambientLight intensity={0.65} /><pointLight position={[3, 3, 4]} intensity={1.4} color="#5be9ff" />
      <Stars radius={32} depth={18} count={850} factor={2} saturation={0} fade speed={0.35} />
      <Core state={state} knowledgeCount={knowledgeCount} />
      <ActivityGraph activity={activity} selectedNodeId={selectedNodeId} onNodeSelect={onNodeSelect} />
      <OrbitControls enablePan={false} minDistance={4} maxDistance={10} rotateSpeed={0.7} />
    </Canvas>
  </div>;
}
