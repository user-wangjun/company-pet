Created At: 2026-05-29T16:26:31Z
Completed At: 2026-05-29T16:26:31Z
File Path: `file:///D:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 108
Total Bytes: 3548
Showing lines 1 to 108
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: import {
2:   MARKETING_FILE_NAME,
3:   socialLinks,
4:   type SocialLink,
5: } from "./marketingContent";
6: 
7: function SocialIcon({ link }: { link: SocialLink }) {
8:   const className = `marketing-social-icon marketing-social-${link.icon}`;
9: 
10:   if (link.icon === "discord") {
11:     return (
12:       <span className={className} role="img" aria-label={link.label} title={link.label}>
13:         <svg viewBox="0 0 64 64" aria-hidden="true">
14:           <path d="M21 20c7-3 15-3 22 0l5 18c-4 4-8 6-13 7l-2-4h-2l-2 4c-5-1-9-3-13-7l5-18Z" />
15:           <circle cx="25" cy="32" r="3" />
16:           <circle cx="39" cy="32" r="3" />
17:           <path d="M27 39c3 2 7 2 10 0" />
18:         </svg>
19:       </span>
20:     );
21:   }
22: 
23:   if (link.icon === "x") {
24:     return (
25:       <span className={className} role="img" aria-label={link.label} title={link.label}>
26:         <svg viewBox="0 0 64 64" aria-hidden="true">
27:           <path d="M16 14l33 36M49 14 15 50" />
28:         </svg>
29:       </span>
30:     );
31:   }
32: 
33:   if (link.icon === "wechat") {
34:     return (
35:       <span className={className} role="img" aria-label={link.label} title={link.label}>
36:         <svg viewBox="0 0 64 64" aria-hidden="true">
37:           <path d="M26 21c-9 0-16 6-16 14 0 4 2 7 5 10l-2 6 7-3c2 1 4 1 6 1 9 0 16-6 16-14S35 21 26 21Z" />
38:           <path d="M39 28c8 0 15 6 15 13 0 4-2 7-5 9l2 5-6-2c-2 1-4 1-6 1-8 0-15-6-15-13" />
39:           <circle cx="21" cy="34" r="1.9" />
40:           <circle cx="31" cy="34" r="1
<truncated 442 bytes>
x="37" cy="28" r="2.2" />
53:           <path d="M27 39c3 3 7 3 10 0" />
54:         </svg>
55:       </span>
56:     );
57:   }
58: 
59:   return (
60:     <span className={className} role="img" aria-label={link.label} title={link.label}>
61:       <svg viewBox="0 0 64 64" aria-hidden="true">
62:         <circle cx="32" cy="32" r="25" />
63:         <circle cx="32" cy="24" r="9" />
64:         <path d="M17 50c4-10 26-10 30 0" />
65:       </svg>
66:     </span>
67:   );
68: }
69: 
70: function MarketingPage() {
71:   const homeHref =
72:     typeof window !== "undefined" &&
73:     window.location.pathname.toLowerCase().endsWith(MARKETING_FILE_NAME)
74:       ? `./${MARKETING_FILE_NAME}`
75:       : "/marketing";
76: 
77:   return (
78:     <main className="marketing-page">
79:       <section className="marketing-browser" aria-label="愈心桌宠宣传首页">
80:         <header className="marketing-topbar">
81:           <a className="marketing-brand" href={homeHref} aria-label="愈心桌宠首页">
82:             <span className="marketing-brand-text">愈心桌宠</span>
83:             <span className="marketing-brand-spark" aria-hidden="true" />
84:           </a>
85: 
86:           <nav className="marketing-socials" aria-label="社交入口">
87:             {socialLinks.map((link) => (
88:               <SocialIcon key={link.label} link={link} />
89:             ))}
90:           </nav>
91:         </header>
92: 
93:         <section className="marketing-hero" aria-label="宇宙星球主视觉">
94:           <div
95:             className="marketing-hero-art"
96:             role="img"
97:             aria-label="彩色星空主视觉"
98:           />
99:           <div className="marketing-planet-float" aria-hidden="true" />
100:           <h1 className="marketing-hidden-title">愈心桌宠</h1>
101:         </section>
102:       </section>
103:     </main>
104:   );
105: }
106: 
107: export default MarketingPage;
108: 
The above content shows the entire, complete file contents of the requested file.
