Created At: 2026-05-30T08:57:02Z
Completed At: 2026-05-30T08:57:02Z
File Path: `file:///d:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 164
Total Bytes: 5089
Showing lines 1 to 164
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
1: import {
2:   useEffect,
3:   useRef,
4:   useState,
5:   type CSSProperties,
6:   type PointerEvent,
7: } from "react";
8: import {
9:   MARKETING_FILE_NAME,
10:   socialLinks,
11: } from "./marketingContent";
12: 
13: const MARKETING_BASE_ART = "./marketing-assets/marketing-base.png";
14: const MARKETING_FLOATERS_ART =
15:   "./marketing-assets/yuxin-floating-motion.png";
16: const MARKETING_CLOUDS_ART = "./marketing-assets/yuxin-clouds-clean.png";
17: 
18: const hotspotCopy = [
19:   {
20:     id: "cat",
21:     className: "marketing-hotspot-cat",
22:     label: "趴在星球上的小猫",
23:     bubble: "欢迎来到愈心宇宙。",
24:   },
25:   {
26:     id: "earth",
27:     className: "marketing-hotspot-earth",
28:     label: "漂浮的愈心星球",
29:     bubble: "星球在呼吸，桌宠也会陪你慢慢恢复能量。",
30:   },
31:   {
32:     id: "ufo",
33:     className: "marketing-hotspot-ufo",
34:     label: "蓝色飞碟兔",
35:     bubble: "正在巡航你的桌面。",
36:   },
37:   {
38:     id: "bunny",
39:     className: "marketing-hotspot-bunny",
40:     label: "星环兔",
41:     bubble: "收到一颗快乐信号。",
42:   },
43: ] as const;
44: 
45: function MarketingPage() {
46:   const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
47:   const [parallax, setParallax] = useState({ x: 0, y: 0 });
48:   const hotspotTimerRef = useRef<number | null>(null);
49:   const homeHref =
50:     typeof window !== "undefined" &&
51:     window.location.pathname.toLowerCase().endsWith(MARKETING_FILE_NAME
<truncated 2263 bytes>
motion-layer marketing-motion-floaters" aria-hidden="true" />
118:         <div className="marketing-motion-layer marketing-motion-clouds marketing-motion-clouds-a" aria-hidden="true" />
119:         <div className="marketing-motion-layer marketing-motion-clouds marketing-motion-clouds-b" aria-hidden="true" />
120: 
121:         <a
122:           className="marketing-polished-hit marketing-polished-brand-hit"
123:           href={homeHref}
124:           aria-label="愈心桌宠首页"
125:         />
126: 
127:         <nav className="marketing-polished-socials" aria-label="社交入口">
128:           {socialLinks.map((link) => (
129:             <span
130:               key={link.label}
131:               className={`marketing-polished-social marketing-polished-social-${link.icon}`}
132:               role="img"
133:               aria-label={link.label}
134:               title={link.label}
135:             />
136:           ))}
137:         </nav>
138: 
139:         <div className="marketing-hotspot-layer">
140:           {hotspotCopy.map((hotspot) => (
141:             <button
142:               key={hotspot.id}
143:               type="button"
144:               className={`marketing-hotspot ${hotspot.className}${
145:                 activeHotspot === hotspot.id ? " is-active" : ""
146:               }`}
147:               aria-label={hotspot.label}
148:               onClick={() => activateHotspot(hotspot.id)}
149:             >
150:               <span className="marketing-hotspot-bubble">{hotspot.bubble}</span>
151:             </button>
152:           ))}
153:         </div>
154: 
155:         <h1 className="marketing-screen-reader-text">愈心桌宠</h1>
156:         <p className="marketing-screen-reader-text">彩色星空主视觉</p>
157:         <p className="marketing-screen-reader-text">宇宙星球主视觉</p>
158:       </section>
159:     </main>
160:   );
161: }
162: 
163: export default MarketingPage;
164: 
The above content shows the entire, complete file contents of the requested file.
