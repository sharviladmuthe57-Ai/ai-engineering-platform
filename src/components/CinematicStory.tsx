"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUpRight, Pause, Play } from "lucide-react";
import { siteConfig } from "@/config/site";
import { usePinnedProgress } from "@/hooks/usePinnedProgress";

export function CinematicStory() {
  const { ref, active, choose, visible, reduced } = usePinnedProgress(7);
  const videos = useRef<(HTMLVideoElement | null)[]>([]);
  const [paused, setPaused] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const shouldPlay = visible && !paused && !reduced;

  useEffect(() => {
    let cancelled = false;
    videos.current.forEach((video, index) => {
      if (!video) return;
      if (index !== active || !shouldPlay) { video.pause(); return; }
      video.muted = true;
      video.play().then(() => { if (!cancelled) setBlocked(false); }).catch(() => { if (!cancelled) setBlocked(true); });
    });
    return () => { cancelled = true; videos.current.forEach(video => video?.pause()); };
  }, [active, shouldPlay]);

  return <section className="cinematic" ref={ref} id="top" data-scene={active + 1} aria-label="Seven chapters of engineering design">
    <div className="cinematicSticky">
      <div className="cinema-media" aria-hidden="true">
        {siteConfig.scenes.map((scene, index) => <div key={scene.id} className={`scene ${active === index ? "active" : ""}`}>
          <img src={`/videos/poster-${scene.id}.webp`} alt="" className="scene-poster" fetchPriority={index === 0 ? "high" : "auto"} loading={index === 0 ? "eager" : "lazy"}/>
          {Math.abs(index - active) <= 1 && !reduced && <video
            ref={node => { videos.current[index] = node; }} src={scene.src}
            muted playsInline loop autoPlay={index === active && shouldPlay}
            preload={index === active ? "auto" : "metadata"}
            onCanPlay={event => { if (index === active && shouldPlay) event.currentTarget.play().catch(() => setBlocked(true)); }}
          />}
        </div>)}
        <div className="cinema-shade"/>
      </div>
      <div className="cinema-content section-shell">
        <div className="hero-topline"><span className="status-dot"/> AI-native engineering <span>Starting with electrical</span></div>
        <div className={`hero-composition ${active === 0 ? "opening" : ""}`}>
          <div className="hero-copy">
            {active === 0 ? <><h1>From drawing.<br/>To electrical<br/><em>design.</em></h1><p>An engineering first draft from your architectural plan. Components, routes, and quantities—ready for an engineer to review.</p></> : <><span className="chapter-label">Chapter {String(active + 1).padStart(2, "0")} / 07</span><h2 key={active}>{siteConfig.scenes[active].title.join(" ")}</h2><p>{siteConfig.scenes[active].detail || "Every new tool changes what we can build. The next step begins with understanding the drawing."}</p></>}
            <div className="cta-row"><a className="button primary" href="#product">Explore the prototype <ArrowUpRight/></a><a className="text-link" href="#feedback">Share your workflow <ArrowUpRight/></a></div>
          </div>
        </div>
        <div className="cinema-bottom">
          <div className="chapter-controls" aria-label="Choose cinematic chapter">{siteConfig.scenes.map((scene,index) => <button key={scene.id} onClick={() => choose(index)} aria-label={`Scene ${scene.id}`} aria-current={index === active ? "step" : undefined}><span>{String(scene.id).padStart(2,"0")}</span><i/></button>)}</div>
          <span className="scroll-hint"><ArrowDown/> Scroll to follow the story</span>
          <button className="play-toggle" onClick={() => { setPaused(!paused); if(blocked) { setPaused(false); videos.current[active]?.play().then(() => setBlocked(false)).catch(() => setBlocked(true)); } }} aria-label={paused || blocked ? "Play cinematic video" : "Pause cinematic video"} disabled={reduced}>{paused || blocked ? <Play/> : <Pause/>}</button>
        </div>
      </div>
    </div>
  </section>;
}
