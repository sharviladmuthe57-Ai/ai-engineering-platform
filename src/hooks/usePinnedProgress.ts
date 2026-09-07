"use client";

import { useMotionValue, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";

/** Measure document scrolling once per requested frame, with no perpetual loop. */
export function usePinnedProgress(count: number, mobileStatic = false) {
  const ref = useRef<HTMLElement>(null);
  const progress = useMotionValue(0);
  const reduced = useReducedMotion();
  const [active, setActive] = useState(0);
  const [visible, setVisible] = useState(false);
  const [manual, setManual] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const mobile = window.matchMedia("(max-width: 700px)");
    let frame = 0;
    const measure = () => {
      frame = 0;
      const isManual = !!reduced || (mobileStatic && mobile.matches);
      setManual(isManual);
      const rect = element.getBoundingClientRect();
      setVisible(rect.bottom > 0 && rect.top < window.innerHeight && !document.hidden);
      if (isManual) return;
      const value = Math.max(0, Math.min(1, -rect.top / Math.max(1, rect.height - window.innerHeight)));
      progress.set(value);
      setActive(Math.min(count - 1, Math.floor(value * count)));
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(measure); };
    const resize = new ResizeObserver(schedule);
    resize.observe(element);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    window.addEventListener("pageshow", schedule);
    document.addEventListener("visibilitychange", schedule);
    mobile.addEventListener("change", schedule);
    measure();
    return () => {
      cancelAnimationFrame(frame);
      resize.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      window.removeEventListener("pageshow", schedule);
      document.removeEventListener("visibilitychange", schedule);
      mobile.removeEventListener("change", schedule);
    };
  }, [count, mobileStatic, progress, reduced]);

  const choose = useCallback((index: number) => {
    const value = (index + 0.5) / count;
    if (manual) { progress.set(value); setActive(index); return; }
    const element = ref.current;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    window.scrollTo({ top: window.scrollY + rect.top + value * (rect.height - window.innerHeight), behavior: "instant" });
  }, [count, manual, progress]);

  return { ref, progress, active, choose, visible, reduced: !!reduced, manual };
}
