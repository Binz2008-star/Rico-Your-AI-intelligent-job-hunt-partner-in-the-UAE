import React from 'react';
import { cn } from '@/lib/utils';
import { MaterialIcon } from './MaterialIcon';

interface CommandInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  placeholder?: string;
  showIcon?: boolean;
  icon?: string;
}

export const CommandInput = React.forwardRef<HTMLInputElement, CommandInputProps>(
  ({ className, placeholder = "Initiate directive...", showIcon = true, icon = "keyboard_double_arrow_right", ...props }, ref) => {
    return (
      <div className="relative group">
        <input
          ref={ref}
          type="text"
          placeholder={placeholder}
          className={cn(
            'w-full bg-transparent border-b border-white/10',
            'py-10 text-4xl font-thin',
            'focus:ring-0 focus:border-primary/60',
            'transition-all duration-1000',
            'placeholder:text-white/5',
            className
          )}
          {...props}
        />
        <div className="absolute right-0 bottom-12 flex items-center gap-4">
          <span className="text-[10px] uppercase tracking-widest text-primary/40 group-hover:text-primary transition-all duration-700">
            Awaiting Command
          </span>
          {showIcon && (
            <MaterialIcon icon={icon} className="text-primary/40 group-hover:text-primary transition-all duration-1000" />
          )}
        </div>
      </div>
    );
  }
);

CommandInput.displayName = 'CommandInput';
