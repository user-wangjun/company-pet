Created At: 2026-05-30T09:38:20Z
Completed At: 2026-05-30T09:38:21Z

				The command completed successfully.
				Output:
				CONTENT: Created At: 2026-05-30T09:01:37Z
Completed At: 2026-05-30T09:01:37Z
File Path: `file:///d:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 176
Total Bytes: 5502
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
22:     label: "ſ�ϵ�Сè",
23:     bubble: "�ӭ�档",
24:   },
25:   {
26:     id: "earth",
27:     className: "marketing-hotspot-earth",
28:     label: "Ư�",
29:     bubble: "�ں�Ҳ�ָ�",
30:   },
31:   {
32:     id: "ufo",
33:     className: "marketing-hotspot-ufo",
34:     label: "�ɫ�ɵ�",
35:     bubble: "�Ѳ�档",
36:   },
37:   {
38:     id: "bunny",
39:     className: "marketing-hotspot-bunny",
40:     label: "�ǻ�",
41:     bubble: "�յ�һ�ſ�źš�",
42:   },
43: ] as const;
44: 
45: function MarketingPage() {
46:   const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
47:   const [parallax, setParallax] = useState({ x: 0, y: 0 });
48:   const hotspotTimerRef = useRef<number | null>(null);
49:   const homeHref =
50:     typeof window !== "u
<truncated 149 bytes>
arketing-motion-clouds marketing-motion-clouds-b" aria-hidden="true" />
120: 
121:         <a
122:           className="marketing-polished-hit marketing-polished-brand-hit"
123:           href={homeHref}
124:           aria-label="�ҳ"
125:         />
126: 
127:         <nav className="marketing-polished-socials" aria-label="�罻�">
128:           {socialLinks.map((link) =>
129:             link.href ? (
130:               <a
131:                 key={link.label}
132:                 className={`marketing-polished-social marketing-polished-social-${link.icon}`}
133:                 href={link.href}
134:                 target="_blank"
135:                 rel="noopener noreferrer"
136:                 aria-label={link.label}
137:                 title={link.label}
138:               />
139:             ) : (
140:               <span
141:                 key={link.label}
142:                 className={`marketing-polished-social marketing-polished-social-${link.icon}`}
143:                 role="img"
144:                 aria-label={link.label}
145:                 title={link.label}
146:               />
147:             )
148:           )}
149:         </nav>
150: 
151:         <div className="marketing-hotspot-layer">
152:           {hotspotCopy.map((hotspot) => (
153:             <button
154:               key={hotspot.id}
155:               type="button"
156:               className={`marketing-hotspot ${hotspot.className}${
157:                 activeHotspot === hotspot.id ? " is-active" : ""
158:               }`}
159:               aria-label={hotspot.label}
160:               onClick={() => activateHotspot(hotspot.id)}
161:             >
162:               <span className="marketing-hotspot-bubble">{hotspot.bubble}</span>
163:             </button>
164:           ))}
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.


