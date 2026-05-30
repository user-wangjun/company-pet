Created At: 2026-05-30T09:01:43Z
Completed At: 2026-05-30T09:01:43Z
File Path: `file:///d:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 178
Total Bytes: 5637
Showing lines 1 to 178
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
17: const WECHAT_QRCODE_ART = "./marketing-assets/wechat-qrcode.jpg";
18: 
19: const hotspotCopy = [
20:   {
21:     id: "cat",
22:     className: "marketing-hotspot-cat",
23:     label: "趴在星球上的小猫",
24:     bubble: "欢迎来到愈心宇宙。",
25:   },
26:   {
27:     id: "earth",
28:     className: "marketing-hotspot-earth",
29:     label: "漂浮的愈心星球",
30:     bubble: "星球在呼吸，桌宠也会陪你慢慢恢复能量。",
31:   },
32:   {
33:     id: "ufo",
34:     className: "marketing-hotspot-ufo",
35:     label: "蓝色飞碟兔",
36:     bubble: "正在巡航你的桌面。",
37:   },
38:   {
39:     id: "bunny",
40:     className: "marketing-hotspot-bunny",
41:     label: "星环兔",
42:     bubble: "收到一颗快乐信号。",
43:   },
44: ] as const;
45: 
46: function MarketingPage() {
47:   const [isWeChatModalOpen, setIsWeChatModalOpen] = useState(false);
48:   const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
49:   const [parallax, setParallax] = useState({ x: 0, y: 0 });
50:   const hotspotTimerRef = useRef<number | null>(nul
<truncated 2882 bytes>
心桌宠首页"
127:         />
128: 
129:         <nav className="marketing-polished-socials" aria-label="社交入口">
130:           {socialLinks.map((link) =>
131:             link.href ? (
132:               <a
133:                 key={link.label}
134:                 className={`marketing-polished-social marketing-polished-social-${link.icon}`}
135:                 href={link.href}
136:                 target="_blank"
137:                 rel="noopener noreferrer"
138:                 aria-label={link.label}
139:                 title={link.label}
140:               />
141:             ) : (
142:               <span
143:                 key={link.label}
144:                 className={`marketing-polished-social marketing-polished-social-${link.icon}`}
145:                 role="img"
146:                 aria-label={link.label}
147:                 title={link.label}
148:               />
149:             )
150:           )}
151:         </nav>
152: 
153:         <div className="marketing-hotspot-layer">
154:           {hotspotCopy.map((hotspot) => (
155:             <button
156:               key={hotspot.id}
157:               type="button"
158:               className={`marketing-hotspot ${hotspot.className}${
159:                 activeHotspot === hotspot.id ? " is-active" : ""
160:               }`}
161:               aria-label={hotspot.label}
162:               onClick={() => activateHotspot(hotspot.id)}
163:             >
164:               <span className="marketing-hotspot-bubble">{hotspot.bubble}</span>
165:             </button>
166:           ))}
167:         </div>
168: 
169:         <h1 className="marketing-screen-reader-text">愈心桌宠</h1>
170:         <p className="marketing-screen-reader-text">彩色星空主视觉</p>
171:         <p className="marketing-screen-reader-text">宇宙星球主视觉</p>
172:       </section>
173:     </main>
174:   );
175: }
176: 
177: export default MarketingPage;
178: 
The above content shows the entire, complete file contents of the requested file.
