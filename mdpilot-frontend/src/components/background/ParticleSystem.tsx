// mdpilot-frontend/src/components/background/ParticleSystem.tsx
import { Canvas, useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';

const PARTICLE_COUNT = 600;

const COLOR_PALETTE = [
  new THREE.Color('#FF6B9D'), // 粉色
  new THREE.Color('#00D4FF'), // 青色
  new THREE.Color('#FFB84D'), // 橙色
];

/**
 * 粒子组件
 * 600个粒子,3种颜色,持续旋转
 */
function Particles() {
  const ref = useRef<THREE.Points>(null);

  // 生成600个随机粒子位置和颜色
  const particles = useMemo(() => {
    const positions = new Float32Array(PARTICLE_COUNT * 3);
    const colors = new Float32Array(PARTICLE_COUNT * 3);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      // 随机位置（球形分布）
      const radius = Math.random() * 2 + 1;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(Math.random() * 2 - 1);

      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);

      // 随机颜色
      const color = COLOR_PALETTE[Math.floor(Math.random() * COLOR_PALETTE.length)];
      colors[i * 3] = color.r;
      colors[i * 3 + 1] = color.g;
      colors[i * 3 + 2] = color.b;
    }
    return { positions, colors };
  }, []);

  // 动画：持续旋转
  useFrame(() => {
    if (ref.current) {
      ref.current.rotation.x += 0.0003;
      ref.current.rotation.y += 0.0005;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
       attach="attributes-position"
          count={particles.positions.length / 3}
          array={particles.positions}
          itemSize={3}
     />
        <bufferAttribute
          attach="attributes-color"
          count={particles.colors.length / 3}
          array={particles.colors}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial
        transparent
        vertexColors
        size={0.8}
        sizeAttenuation
        depthWrite={false}
        opacity={0.6}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

/**
 * 粒子系统容器
 * 提供Canvas和相机配置
 */
export function ParticleSystem(): JSX.Element {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none">
      <Canvas camera={{ position: [0, 0, 3], fov: 75 }}>
        <Particles />
      </Canvas>
    </div>
  );
}
