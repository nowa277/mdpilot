import { cn } from '@shared/utils';
import { type ButtonHTMLAttributes,forwardRef } from 'react';

export interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  'aria-label': string;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { className, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
    'inline-flex h-8 w-8 items-center justify-center rounded-chip text-text-2 hover:bg-bg-2 hover:text-text-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-1',
    className,
      )}
      {...rest}
    />
  );
});
