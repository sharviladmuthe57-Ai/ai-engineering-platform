"use client";

import { motion, useTransform } from "framer-motion";
import { ScanLine, ArrowDown } from "lucide-react";
import { usePinnedProgress } from "@/hooks/usePinnedProgress";

const stages = [
  { title: "Input", detail: "Start with the architectural drawing.", image: "/product/site-01-architectural-input.png" },
  { title: "Understand", detail: "Read the spaces behind the lines.", image: "/product/site-02-geometry-extraction.png" },
  { title: "Structure", detail: "Turn geometry into a starting point for engineering.", image: "/product/site-03-structured-plan.png" },
];

export function ProductStory() {
  const { ref, progress, active, choose, manual, reduced, visible } = usePinnedProgress(3, true);
  const firstWipe = useTransform(progress, [.24, .43], ["inset(0 100% 0 0)", "inset(0 0% 0 0)"]);
  const secondWipe = useTransform(progress, [.58, .77], ["inset(0 100% 0 0)", "inset(0 0% 0 0)"]);
  const scan = useTransform(progress, [.24, .43, .58, .77], ["0%", "100%", "0%", "100%"]);
  return <section id="product" className="pinned-story product-story" ref={ref} data-stage={active + 1}>
    <div className="story-sticky section-shell">
      <div className="demo-heading"><div><p className="section-kicker"><ScanLine/> 01 / Architectural understanding</p><h2>The drawing. <em>Understood.</em></h2></div><p>From pixels to spatial information.<br/>One plan. Three stages of interpretation.</p></div>
      <div className="plan-frame">
        <div className="app-bar"><span className="window-dots"><i/><i/><i/></span><span>Architectural canvas</span><span className="frame-status">{String(active + 1).padStart(2,"0")} / {stages[active].title}</span></div>
        <div className="aligned-plans">
          {stages.map((stage,index) => {
            const props = { src:stage.image, width:1400, height:1000, alt:`${stage.title}: ${stage.detail}`, "aria-hidden":index!==active };
            return manual ? <img key={stage.image} {...props} loading={visible?"eager":"lazy"} style={{clipPath:active>=index?"inset(0 0 0 0)":"inset(0 100% 0 0)"}}/>
              : <motion.img key={stage.image} {...props} loading={visible?"eager":"lazy"} style={{clipPath:index===1?firstWipe:index===2?secondWipe:undefined}}/>;
          })}
          {!manual && !reduced && <motion.div className="scan-cursor" style={{left:scan}}/>}
          <span className="canvas-note">Prototype interpretation · engineer review required</span>
        </div>
      </div>
      <div className="demo-bottom"><div className="stage-tabs" aria-label="Plan transformation stages">{stages.map((stage,index) => <button key={stage.title} aria-current={active === index ? "step" : undefined} onClick={() => choose(index)}><span>0{index + 1}</span>{stage.title}</button>)}</div><p>{stages[active].detail} <ArrowDown/></p></div>
    </div>
  </section>;
}
