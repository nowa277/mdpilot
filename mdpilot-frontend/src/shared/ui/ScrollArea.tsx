import { cn } from '@shared/utils';
import { forwardRef, type HTMLAttributes } from 'react';

export const ScrollArea = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  function ScrollArea({ className, ...rest }, ref) {
    return (
      <div
        ref={ref}
        className={cn('overflow-y-auto overflow-x-hidden scrollbar-thin', className)}
        {...rest}
      />
    );
  },
);
