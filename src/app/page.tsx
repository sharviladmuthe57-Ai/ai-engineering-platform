import { ArrowUpRight } from "lucide-react";
import { CinematicStory } from "@/components/CinematicStory";
import { ProductStory } from "@/components/ProductStory";
import { ElectricalStory } from "@/components/ElectricalStory";
import { EditorShowcase } from "@/components/EditorShowcase";
import { VisionStory } from "@/components/VisionStory";
import { FeedbackForm } from "@/components/FeedbackForm";
import { Footer } from "@/components/Footer";
import { Navigation } from "@/components/Navigation";
import { Reveal } from "@/components/Reveal";
import { mailto, siteConfig } from "@/config/site";

const process = [
  ["Read", "Architectural drawing"],
  ["Understand", "Rooms, openings, geometry"],
  ["Design", "Electrical first draft"],
  ["Route", "Architecture-aware wiring"],
  ["Quantify", "Bill of quantities"],
  ["Review", "Engineer edits"],
];

export default function Home() {
  return <main className="site-root">
    <div className="atmosphere" aria-hidden="true"/>
    <Navigation/>
    <CinematicStory/>
    <div className="bridge section-shell"><p>Drawings already hold the information.<br/><strong>We’re building the tools to put it to work.</strong></p><span>Electrical / Working prototype</span></div>
    <ProductStory/>
    <ElectricalStory/>
    <EditorShowcase/>
    <VisionStory/>

    <section className="how-section section-shell" id="approach">
      <Reveal><div className="section-heading"><div><p className="section-kicker">One connected workflow</p><h2>Less redrawing.<br/><em>More engineering.</em></h2></div><p>From architectural input to an editable electrical draft, with the engineer in control.</p></div></Reveal>
      <div className="process-line">{process.map(([title,description],index) => <Reveal key={title} delay={index * .045}><div className="process-node"><span>0{index+1}</span><h3>{title}</h3><p>{description}</p></div></Reveal>)}</div>
    </section>

    <section className="vision-section" id="vision">
      <div className="section-shell vision-grid">
        <Reveal><div className="vision-copy"><p className="section-kicker">The direction</p><h2>One building.<br/><em>Connected<br/>engineering.</em></h2><p>Electrical comes first. Our longer-term vision is a shared model connecting the systems inside every building.</p></div></Reveal>
        <Reveal delay={.1}><div className="discipline-rows"><div className="current-discipline"><h3>Electrical</h3><span><i className="status-dot"/> Building now</span></div>{["Plumbing","HVAC","Structural"].map(name => <div key={name}><h3>{name}</h3><span>Future</span></div>)}</div><p className="vision-next">Longer-term vision<strong>A coordinated engineering model</strong>Interactive 3D and other disciplines are not yet implemented.</p></Reveal>
      </div>
    </section>

    <section className="discovery-section section-shell" id="feedback">
      <div className="discovery-grid">
        <Reveal><div className="discovery-intro"><p className="section-kicker">Build with the people who do the work</p><h2>Your workflow.<br/><em>Our next<br/>conversation.</em></h2><p>We’re speaking with engineering and construction teams. Tell us where the work slows down—and what a useful first draft would need to get right.</p><a href={mailto}>{siteConfig.email}</a></div></Reveal>
        <FeedbackForm/>
      </div>
    </section>

    <section className="final-section section-shell" id="contact">
      <Reveal><p className="section-kicker">Let’s talk</p><h2>The next engineering<br/>workflow starts<br/><em>with a conversation.</em></h2><a className="email-link" href={mailto}>{siteConfig.email}<ArrowUpRight/></a><div className="cta-row"><a className="button primary" href="#feedback">Share your workflow <ArrowUpRight/></a><a className="button secondary" href={mailto}>Email us <ArrowUpRight/></a></div></Reveal>
    </section>
    <Footer/>
  </main>;
}
