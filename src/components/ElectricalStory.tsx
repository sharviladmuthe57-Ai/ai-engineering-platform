"use client";

import { ArrowUpRight, Cable, Check } from "lucide-react";
import { usePinnedProgress } from "@/hooks/usePinnedProgress";
import { EngineeringCanvas, project } from "@/components/EngineeringCanvas";

const steps = ["Architecture", "Components", "Routing", "Quantities"];

export function ElectricalStory() {
  const { ref, active, choose } = usePinnedProgress(4, true);
  return <section id="electrical" className="pinned-story electrical-story" ref={ref} data-stage={active + 1}>
    <div className="story-sticky section-shell">
      <div className="demo-heading"><div><p className="section-kicker"><Cable/> 02 / Electrical generation</p><h2>An engineering <em>first draft.</em></h2></div><p>Place. Route. Quantify.<br/>Keep the design connected.</p></div>
      <div className="electrical-demo">
        <div className="app-bar"><span className="status-dot"/><span>Electrical design / plan 01</span><span className="frame-status">Real generated result</span></div>
        <div className="electrical-workspace"><div className="electrical-drawing"><EngineeringCanvas stage={active}/><div className="drawing-legend"><span><i/> Components</span><span><i/> Routes</span><span>Engineer review required</span></div></div>
          <aside className={`boq-panel ${active >= 3 ? "shown" : ""}`} aria-hidden={active < 3}>
            <div className="boq-title"><span>Bill of quantities</span><Check/></div><div className="wire-total"><strong>{project.totalWire.toFixed(2)}<small> m</small></strong><span>Estimated wire length</span></div>
            <div className="boq-table"><table><thead><tr><th>Item</th><th>Qty</th></tr></thead><tbody>{project.bom.map(item => <tr key={item.item}><td>{item.item}</td><td>{item.qty} <small>{item.unit}</small></td></tr>)}</tbody></table></div>
            <p>Prototype quantities, subject to engineering validation.</p>
          </aside>
        </div>
      </div>
      <div className="demo-bottom"><div className="stage-tabs" aria-label="Electrical output stages">{steps.map((step,index) => <button key={step} aria-current={active === index ? "step" : undefined} onClick={() => choose(index)}><span>0{index + 1}</span>{step}</button>)}</div><a className="text-link" href="/product/electrical-routing-boq.png" target="_blank" rel="noreferrer">View original output <ArrowUpRight/></a></div>
    </div>
  </section>;
}
