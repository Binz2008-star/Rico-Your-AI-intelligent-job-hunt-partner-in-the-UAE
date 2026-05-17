import { cn } from '@/lib/utils';
import React from 'react';

interface MaterialIconProps extends React.HTMLAttributes<HTMLSpanElement> {
    icon: string;
    filled?: boolean;
    weight?: 100 | 200 | 300 | 400 | 500 | 600 | 700;
    size?: number;
}

export const MaterialIcon = React.forwardRef<HTMLSpanElement, MaterialIconProps>(
    ({ icon, filled = false, weight = 300, size = 24, className, style, ...props }, ref) => {
        const fontVariationSettings = `'FILL' ${filled ? '1' : '0'}, 'wght' ${weight}, 'GRAD' 0, 'opsz' ${size}`;

        return (
            <span
                ref={ref}
                className={cn('material-symbols-outlined', className)}
                style={{
                    fontVariationSettings,
                    fontSize: `${size}px`,
                    ...style,
                }}
                {...props}
            >
                {icon}
            </span>
        );
    }
);

MaterialIcon.displayName = 'MaterialIcon';
