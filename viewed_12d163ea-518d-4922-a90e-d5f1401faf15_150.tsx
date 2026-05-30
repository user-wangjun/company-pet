Created At: 2026-05-30T09:06:09Z
Completed At: 2026-05-30T09:06:10Z
File Path: `file:///d:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 224
Total Bytes: 7253
Showing lines 35 to 65
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
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
50:   const hotspotTimerRef = useRef<number | null>(null);
51:   const homeHref =
52:     typeof window !== "undefined" &&
53:     window.location.pathname.toLowerCase().endsWith(MARKETING_FILE_NAME)
54:       ? `./${MARKETING_FILE_NAME}`
55:       : "/marketing";
56: 
57:   useEffect(() => {
58:     return () => {
59:       if (hotspotTimerRef.current !== null) {
60:         window.clearTimeout(hotspotTimerRef.current);
61:       }
62:     };
63:   }, []);
64: 
65:   const handlePointerMove = (event: PointerEvent<HTMLElement>) => {
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
