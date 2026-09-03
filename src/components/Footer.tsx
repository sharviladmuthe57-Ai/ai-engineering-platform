import { mailto,siteConfig } from "@/config/site";
export function Footer(){return <footer><div><span className="mark"/>{siteConfig.companyName}</div><nav aria-label="Footer">{siteConfig.navigation.map(x=><a key={x.href} href={x.href}>{x.label}</a>)}<a href={mailto}>Contact</a></nav><a href={mailto}>{siteConfig.email}</a><small>© 2026 {siteConfig.companyName}</small></footer>}
