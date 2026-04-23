import { motion } from "framer-motion";

export function TalkingBars({ active = false }: { active?: boolean }) {
  return (
    <div data-testid="talking-bars" className="flex items-end gap-1.5">
      {[0, 1, 2, 3].map((index) => (
        <motion.span
          key={index}
          animate={
            active
              ? {
                  height: [8, 18 + (index % 2) * 5, 10, 20 - (index % 2) * 4, 8],
                }
              : { height: 8 }
          }
          transition={{
            duration: 1.1,
            repeat: active ? Infinity : 0,
            ease: "easeInOut",
            delay: index * 0.05,
          }}
          className="block w-[3px] rounded-full bg-current"
        />
      ))}
    </div>
  );
}
