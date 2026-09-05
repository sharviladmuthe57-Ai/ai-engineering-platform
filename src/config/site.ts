export const siteConfig = {
  companyName: "PROJECT NAME",
  email: "sharviladmuthe57@gmail.com",
  phone: "",
  linkedin: "",
  github: "",
  titleSuffix: "AI Engineering Design",
  description:
    "AI-native engineering design, starting with electrical systems generated from architectural drawings.",
  navigation: [
    { label: "Product", href: "#product" },
    { label: "How it works", href: "#approach" },
    { label: "Vision", href: "#vision" },
    { label: "Feedback", href: "#feedback" },
  ],
  scenes: [
    { id: 1, src: "/videos/scene-01.mp4", title: ["WE HAVE ALWAYS DESIGNED", "BEFORE WE BUILT."], detail: "" },
    { id: 2, src: "/videos/scene-02.mp4", title: ["DRAW.", "MEASURE.", "BUILD."], detail: "" },
    { id: 3, src: "/videos/scene-03.mp4", title: ["DRAWINGS BECAME", "ENGINEERING DOCUMENTS."], detail: "" },
    { id: 4, src: "/videos/scene-04.mp4", title: ["PAPER MOVED", "TO SOFTWARE."], detail: "The tools changed. The workflow remained deeply manual." },
    { id: 5, src: "/videos/scene-05.mp4", title: ["NOW THE DRAWING", "CAN BE UNDERSTOOD."], detail: "From lines and pixels to structured building information." },
    { id: 6, src: "/videos/scene-06.mp4", title: ["THE NEXT ERA OF", "ENGINEERING DESIGN."], detail: "" },
    { id: 7, src: "/videos/scene-07.mp4", title: ["FROM DRAWING", "TO ENGINEERING."], detail: "Starting with electrical. Building toward AI-native engineering design." },
  ],
} as const;

export const mailto = `mailto:${siteConfig.email}`;
