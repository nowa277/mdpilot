import { useCallback, useEffect, useRef, useState } from 'react';

interface ResizableHandleProps {
  onResize: (delta: number) => void;
  currentWidth: number;
}

export function ResizableHandle({
  onResize,
  currentWidth
}: ResizableHandleProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
    startXRef.current = e.clientX;
    startWidthRef.current = currentWidth;
  }, [currentWidth]);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const delta = e.clientX - startXRef.current;
      onResize(delta);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, onResize]);

  return (
    <div
      className="relative flex items-center justify-center"
      style={{
        width: '8px',
        cursor: 'col-resize',
        userSelect: 'none'
      }}
      onMouseDown={handleMouseDown}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Gradient line background */}
      <div
        className="absolute"
        style={{
          width: '2px',
          height: '100%',
          background: 'linear-gradient(180deg, transparent 0%, rgba(0, 207, 170, 0.3) 50%, transparent 100%)',
          boxShadow: '0 0 8px rgba(0, 207, 170, 0.2)'
        }}
      />

      {/* Glow bar indicator */}
      <div
        style={{
          width: '3px',
          height: isDragging ? '64px' : '48px',
          background: 'linear-gradient(180deg, transparent, rgba(0, 207, 170, 0.6), transparent)',
          borderRadius: '2px',
          boxShadow: isDragging
            ? '0 0 24px rgba(0, 207, 170, 0.9)'
            : isHovered
              ? '0 0 20px rgba(0, 207, 170, 0.7)'
              : '0 0 12px rgba(0, 207, 170, 0.5)',
          opacity: isHovered || isDragging ? 1 : 0.8,
          transition: 'all 0.2s ease',
          zIndex: 1
        }}
      />
    </div>
  );
}
