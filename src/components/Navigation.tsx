"use client";

import { Menu, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { siteConfig } from "@/config/site";

export function Navigation() {
  const [open,setOpen] = useState(false);
  const [scrolled,setScrolled] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); toggle.current?.focus(); } };
    onScroll();
    window.addEventListener("scroll", onScroll, {passive:true});
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("scroll",onScroll); window.removeEventListener("keydown",onKey); };
  }, []);
  return <header className={`nav ${scrolled ? "scrolled" : ""}`}>
    <a href="#top" className="wordmark" aria-label={`${siteConfig.companyName} home`}><span className="mark"/>{siteConfig.companyName}</a>
    <a className="nav-workflow text-link" href="#feedback">Share your workflow</a>
    <nav id="primary-nav" className={`navLinks ${open ? "open" : ""}`} aria-label="Primary">
      {siteConfig.navigation.map(item => <a key={item.href} href={item.href} onClick={() => setOpen(false)}>{item.label}</a>)}
      <a className="button navCta" href="#contact" onClick={() => setOpen(false)}>Talk to us</a>
    </nav>
    <button ref={toggle} className="menuButton" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="primary-nav" aria-label="Toggle navigation">{open ? <X/> : <Menu/>}</button>
  </header>;
}
