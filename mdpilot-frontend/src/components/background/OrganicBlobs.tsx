// mdpilot-frontend/src/components/background/OrganicBlobs.tsx
import './background-effects.css';

/**
 * 有机Blob组件
 * 3个浮动的有机形状,不同颜色和延迟
 */

type BlobConfig = {
  size: number;
  color: string;
  delay: number;
  top?: string;
  bottom?: string;
  left?: string;
  right?: string;
};

const BLOBS: BlobConfig[] = [
  {
    size: 400,
    color: '#FF6B9D',
    top: '10%',
    left: '10%',
    delay: 0
  },
  {
    size: 350,
    color: '#00D4FF',
    top: '60%',
    right: '15%',
    delay: -7
  },
  {
    size: 300,
    color: '#FFB84D',
    bottom: '15%',
    left: '50%',
    delay: -14
  },
];

export function OrganicBlobs(): JSX.Element {
  return (
    <>
      {BLOBS.map((blob, index) => (
        <div
          key={index}
          className="organic-blob"
          style={{
       width: `${blob.size}px`,
            height: `${blob.size}px`,
            background: blob.color,
            top: blob.top,
            left: blob.left,
            right: blob.right,
        bottom: blob.bottom,
       animationDelay: `${blob.delay}s`,
          }}
          aria-hidden="true"
        />
      ))}
    </>
  );
}
