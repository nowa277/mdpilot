import { cn } from '@shared/utils';
import { type ButtonHTMLAttributes,forwardRef } from 'react';

type Variant = 'primary' | 'ghost' | 'danger';
type Size = 'sm' | 'md';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const VARIANT: Record<Variant, string> = {
  primary: 'bg-accent-1 text-bg-0 hover:brightness-110 disabled:opacity-50',
  ghost: 'bg-transparent text-text-1 hover:bg-bg-2 border border-border-1',
  danger: 'bg-danger text-bg-0 hover:brightness-110',
};

const SIZE: Record<Size, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
      'inline-flex items-center justify-center rounded-card font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-1',
    VARIANT[variant],
        SIZE[size],
        className,
      )}
      {...rest}
    />
  );
});
