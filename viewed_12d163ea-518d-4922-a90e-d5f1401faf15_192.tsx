Created At: 2026-05-30T09:11:36Z
Completed At: 2026-05-30T09:11:36Z
File Path: `file:///d:/CodeWorkspace/%E7%94%B5%E8%84%91%E6%A1%8C%E5%AE%A0/src/marketing/MarketingPage.tsx`
Total Lines: 209
Total Bytes: 6860
Showing lines 40 to 65
The following code has been modified to include a line number before every line, in the format: <line_number>: <original_line>. Please note that any changes targeting the original code should remove the line number, colon, and leading space.
40:     className: "marketing-hotspot-bunny",
41:     label: "星环兔",
42:     bubble: "收到一颗快乐信号。",
43:   },
44: ] as const;
45: 
46: function MarketingPage() {
47:   const [isWeChatActive, setIsWeChatActive] = useState(false);
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
58:     const handleDocumentClick = () => {
59:       setIsWeChatActive(false);
60:     };
61:     document.addEventListener("click", handleDocumentClick);
62: 
63:     return () => {
64:       document.removeEventListener("click", handleDocumentClick);
65:       if (hotspotTimerRef.current !== null) {
The above content does NOT show the entire file contents. If you need to view any lines of the file which were not shown to complete your task, call this tool again to view those lines.
