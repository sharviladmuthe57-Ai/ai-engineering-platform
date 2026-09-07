import { mailto, siteConfig } from "@/config/site";

export function Footer() {
  return <footer className="footer section-shell">
    <div><span className="mark"/>{siteConfig.companyName}</div>
    <nav aria-label="Footer">{siteConfig.navigation.map(item => <a key={item.href} href={item.href}>{item.label}</a>)}</nav>
    <a href={mailto}>{siteConfig.email}</a>
    <small>© 2026 {siteConfig.companyName} · Early working prototype</small>
  </footer>;
}
