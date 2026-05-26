import './background-effects.css';

import { GradientBeams } from './GradientBeams';
import { OrganicBlobs } from './OrganicBlobs';
import { ParticleSystem } from './ParticleSystem';

/**
 * 背景效果主容器
 * 组合所有背景效果组件
 */
export function BackgroundEffects(): JSX.Element {
  return (
    <>
      {/* 渐变光束 */}
      <GradientBeams />

      {/* 有机Blob */}
      <OrganicBlobs />

      {/* Three.js粒子系统 */}
      <ParticleSystem />
    </>
  );
}
