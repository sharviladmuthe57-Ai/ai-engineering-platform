"use client";

import { motion, useReducedMotion } from "framer-motion";

export function Reveal({ children, delay = 0, className = "" }: {
  children: React.ReactNode; delay?: number; className?: string;
}) {
  const reduced = useReducedMotion();
  // Keep meaningful content visible even before hydration or on a fast scroll.
  return <motion.div className={className}
    initial={reduced ? false : { opacity: .78, y: 16 }}
    whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, amount: .08 }}
    transition={{ duration: .5, delay, ease: [.22, 1, .36, 1] }}>
    {children}
  </motion.div>;
}
