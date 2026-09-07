import { ArrowUpRight, Move, Plus, Route } from "lucide-react";
import { Reveal } from "@/components/Reveal";

export function EditorShowcase() {
  return <section id="editor" className="editor-section section-shell">
    <Reveal><div className="section-heading"><div><p className="section-kicker">03 / Editable 2D Canvas V1</p><h2>The first draft<br/>is still <em>yours.</em></h2></div><p>AI prepares the starting point.<br/>The engineer reviews and edits the design.</p></div></Reveal>
    <Reveal><div className="editor-proof-frame"><div className="app-bar"><span className="window-dots"><i/><i/><i/></span><span>Editable Electrical Canvas V1</span><span className="frame-status">Actual workspace export</span></div><div className="editor-embed"><iframe src="/product/editor-v1.html" title="Actual Editable 2D Electrical Canvas V1 showing components, routes, selected properties, and BOQ" loading="lazy" sandbox="" tabIndex={-1}/></div><div className="editor-caption"><span>Recorded project state · editing is available in the local prototype</span><a href="/product/editor-v1.html" target="_blank" rel="noreferrer">Open full preview <ArrowUpRight/></a></div></div></Reveal>
    <div className="editor-annotations">{[{Icon:Move,label:"Drag to move"},{Icon:Plus,label:"Add components"},{Icon:Route,label:"Routes + BOQ update"}].map(({Icon,label}) => <div key={label}><Icon/><span>{label}</span></div>)}</div>
  </section>;
}
