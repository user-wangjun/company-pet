Created At: 2026-05-30T09:06:14Z
Completed At: 2026-05-30T09:06:14Z
The following changes were made by the replace_file_content tool to: d:\CodeWorkspace\电脑桌宠\src\marketing\MarketingPage.tsx. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -44,7 +44,7 @@
 ] as const;
 
 function MarketingPage() {
-  const [isWeChatModalOpen, setIsWeChatModalOpen] = useState(false);
+  const [isWeChatActive, setIsWeChatActive] = useState(false);
   const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
   const [parallax, setParallax] = useState({ x: 0, y: 0 });
   const hotspotTimerRef = useRef<number | null>(null);
@@ -54,7 +54,13 @@
       : "/marketing";
 
   useEffect(() => {
+    const handleDocumentClick = () => {
+      setIsWeChatActive(false);
+    };
+    document.addEventListener("click", handleDocumentClick);
+
     return () => {
+      document.removeEventListener("click", handleDocumentClick);
       if (hotspotTimerRef.current !== null) {
         window.clearTimeout(hotspotTimerRef.current);
       }
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.