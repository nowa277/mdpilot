interface GradientDividerProps {
  orientation?: 'vertical' | 'horizontal';
  className?: string;
}

export function GradientDivider({
  orientation = 'vertical',
  className = ''
}: GradientDividerProps) {
  if (orientation === 'vertical') {
    return (
      <div
        className={`w-[2px] ${className}`}
        style={{
          background: 'linear-gradient(180deg, transparent 0%, rgba(0, 207, 170, 0.3) 50%, transparent 100%)',
          boxShadow: '0 0 8px rgba(0, 207, 170, 0.2)'
        }}
      />
    );
  }

  return (
    <div
      className={`h-[1px] mx-3 ${className}`}
      style={{
        background: 'linear-gradient(90deg, transparent 0%, rgba(0, 207, 170, 0.3) 50%, transparent 100%)',
        boxShadow: '0 0 8px rgba(0, 207, 170, 0.2)'
      }}
    />
  );
}
