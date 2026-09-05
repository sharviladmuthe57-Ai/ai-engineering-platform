"use client";

import { motion, useReducedMotion, useScroll } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const stages = [
  { number: "01", title: "ARCHITECTURAL INPUT", copy: "A real architectural plan enters the workflow.", image: "/product/site-01-architectural-input.png" },
  { number: "02", title: "GEOMETRY EXTRACTION", copy: "The prototype detects spatial structure, room boundaries, and openings.", image: "/product/site-02-geometry-extraction.png" },
  { number: "03", title: "STRUCTURED PLAN STATE", copy: "The drawing becomes usable building information for engineering work.", image: "/product/site-03-structured-plan.png" },
];

export function ProductStory(){
  const ref=useRef<HTMLElement>(null); const reduce=useReducedMotion(); const [active,setActive]=useState(0); const {scrollYProgress}=useScroll({target:ref,offset:["start start","end end"]});
  useEffect(()=>scrollYProgress.on("change",(value)=>setActive(Math.min(2,Math.floor(value*3)))),[scrollYProgress]);
  return <section className="product-story" ref={ref} aria-label="Architectural plan transformation story"><div className="story-sticky"><div className="story-stage-copy">{stages.map((stage,index)=><motion.div key={stage.number} className={index===active?"story-copy active":"story-copy"} animate={{opacity:index===active?1:0,y:index===active?0:12}} transition={{duration:reduce?0:.38}}><span>{stage.number} / 03</span><h3>{stage.title}</h3><p>{stage.copy}</p></motion.div>)}</div><div className="story-frame"><div className="scanline"/><div className="story-label">REAL PROTOTYPE ARTIFACT</div>{stages.map((stage,index)=><motion.img key={stage.image} src={stage.image} alt={index===active?stage.title:""} aria-hidden={index!==active} className={index===active?"active":""} initial={false} animate={{opacity:index===active?1:0,scale:index===active?1:1.025}} transition={{duration:reduce?0:.55,ease:[.22,1,.36,1]}}/>)}</div><div className="story-indicator">{stages.map((stage,index)=><button key={stage.number} type="button" aria-label={`Show ${stage.title}`} aria-current={index===active?"step":undefined} className={index===active?"active":""} onClick={()=>setActive(index)}>{stage.number}</button>)}</div></div></section>
}
