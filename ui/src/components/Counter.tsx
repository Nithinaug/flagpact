import { motion, useSpring, useTransform } from "motion/react";
import { useEffect } from "react";

export function Counter({ value }: { value: number }) {
  const spring = useSpring(0, { stiffness: 300, damping: 30 });
  const text = useTransform(spring, (v) => Math.round(v).toString());
  useEffect(() => {
    spring.set(value);
  }, [spring, value]);
  return <motion.span className="tabular-nums">{text}</motion.span>;
}
