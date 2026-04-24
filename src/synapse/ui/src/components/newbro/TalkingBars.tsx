import { motion } from "framer-motion";

export function TalkingBars({ active = false }: { active?: boolean }) {
  return (
    <div data-testid="talking-bars" className="flex items-end gap-1">
      {[0, 1, 2, 3].map((index) => (
        <motion.span
          key={index}
          animate={
            active
              ? {
                  height: [7, 13 + (index % 2) * 4, 9, 15 - (index % 2) * 2, 7],
                }
              : { height: 8 }
          }
          transition={{
            duration: 1.45,
            repeat: active ? Infinity : 0,
            ease: "easeInOut",
            delay: index * 0.07,
          }}
          className="block w-[2px] rounded-full bg-current"
        />
      ))}
    </div>
  );
}
