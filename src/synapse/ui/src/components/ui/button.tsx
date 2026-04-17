import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[linear-gradient(135deg,#12907a_0%,#0b5748_100%)] text-white shadow-[0_18px_40px_-22px_rgba(11,87,72,0.55)] hover:-translate-y-px",
        secondary:
          "bg-white/85 text-[#1a2a23] shadow-[inset_0_0_0_1px_rgba(30,41,59,0.12)] hover:-translate-y-px",
        ghost: "text-[#5e6d66] hover:bg-white/70 hover:text-[#1a2a23]",
        outline:
          "bg-transparent text-[#1a2a23] shadow-[inset_0_0_0_1px_rgba(30,41,59,0.12)] hover:bg-white/70",
        destructive: "bg-[#cb4d3d] text-white hover:-translate-y-px",
      },
      size: {
        default: "min-h-10 px-4 py-2",
        sm: "min-h-8 px-3 py-2 text-[0.78rem]",
        lg: "min-h-11 px-5 py-3",
        icon: "h-10 w-10 px-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
