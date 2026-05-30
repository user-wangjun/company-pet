Created At: 2026-05-30T09:37:28Z
Completed At: 2026-05-30T09:37:28Z
File Path: `file:///d:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 248
Total Bytes: 8588
Showing lines 1 to 100
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: import { useState, useRef, type PointerEvent } from "react";
2: import {
3:   MARKETING_FILE_NAME,
4:   socialLinks,
5:   type SocialLink,
6: } from "./marketingContent";
7: 
8: function SocialIcon({ link }: { link: SocialLink }) {
9:   const className = `marketing-social-icon marketing-social-${link.icon}`;
10: 
11:   if (link.icon === "discord") {
12:     return (
13:       <span className={className} role="img" aria-label={link.label} title={link.label}>
14:         <svg viewBox="0 0 64 64" aria-hidden="true">
15:           <path d="M21 20c7-3 15-3 22 0l5 18c-4 4-8 6-13 7l-2-4h-2l-2 4c-5-1-9-3-13-7l5-18Z" />
16:           <circle cx="25" cy="32" r="3" />
17:           <circle cx="39" cy="32" r="3" />
18:           <path d="M27 39c3 2 7 2 10 0" />
19:         </svg>
20:       </span>
21:     );
22:   }
23: 
24:   if (link.icon === "x") {
25:     return (
26:       <span className={className} role="img" aria-label={link.label} title={link.label}>
27:         <svg viewBox="0 0 64 64" aria-hidden="true">
28:           <path d="M16 14l33 36M49 14 15 50" />
29:         </svg>
30:       </span>
31:     );
32:   }
33: 
34:   if (link.icon === "wechat") {
35:     return (
36:       <span className={className} role="img" aria-label={link.label} title={link.label}>
37:         <svg viewBox="0 0 64 64" aria-hidden="true">
38:           <path d="M26 21c-9 0-16 6-16 14 0 4 2 7 5 10l-2 6 7-3c2 1 4 1 6 1 9 0 16-6 16-14S35 21 26 21Z" />
39:           <path d="M39 28c8 0 15 6 15 13 0 4-2 7-5 9l2 5-6-2c-2 1-4 1-6 1-8 0-15-
<truncated 493 bytes>
="true">
52:         <circle cx="32" cy="32" r="25" />
53:         <circle cx="32" cy="24" r="9" />
54:         <path d="M17 50c4-10 26-10 30 0" />
55:       </svg>
56:     </span>
57:   );
58: }
59: 
60: function MarketingPage() {
61:   const homeHref =
62:     typeof window !== "undefined" &&
63:     window.location.pathname.toLowerCase().endsWith(MARKETING_FILE_NAME)
64:       ? `./${MARKETING_FILE_NAME}`
65:       : "/marketing";
66: 
67:   return (
68:     <main className="marketing-page">
69:       <section className="marketing-browser" aria-label="愈心桌宠宣传首页">
70:         <header className="marketing-topbar">
71:           <a className="marketing-brand" href={homeHref} aria-label="愈心桌宠首页">
72:             <span className="marketing-brand-text">愈心桌宠</span>
73:             <span className="marketing-brand-spark" aria-hidden="true" />
74:           </a>
75: 
76:           <nav className="marketing-socials" aria-label="社交入口">
77:             {socialLinks.map((link) => (
78:               <SocialIcon key={link.label} link={link} />
79:             ))}
80:           </nav>
81:         </header>
82: 
83:         <section className="marketing-hero" aria-label="宇宙星球主视觉">
84:           <div
85:             className="marketing-hero-art"
86:             role="img"
87:             aria-label="彩色星空主视觉"
88:           />
89:           <div className="marketing-planet-float" aria-hidden="true" />
90:           <h1 className="marketing-hidden-title">愈心桌宠</h1>
91:         </section>
92:       </section>
93:     </main>
94:   );
95: }
96: 
97: export default MarketingPage;
98: 
99: The above content shows the entire, complete file contents of the requested file.
100: 
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
