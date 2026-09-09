import type { Metadata } from "next";
import "./globals.css";
import { siteConfig } from "@/config/site";

export const metadata: Metadata = {
  title: `${siteConfig.companyName} — ${siteConfig.titleSuffix}`,
  description: siteConfig.description,
  openGraph: { title: `${siteConfig.companyName} — ${siteConfig.titleSuffix}`, siteName: siteConfig.companyName, description: siteConfig.description, type: "website" },
  twitter: { card: "summary", title: `${siteConfig.companyName} — ${siteConfig.titleSuffix}`, description: siteConfig.description },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
