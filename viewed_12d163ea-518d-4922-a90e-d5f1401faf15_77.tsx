Created At: 2026-05-30T09:01:41Z
Completed At: 2026-05-30T09:01:41Z
The following changes were made by the replace_file_content tool to: d:\CodeWorkspace\电脑桌宠\src\marketing\MarketingPage.tsx. If relevant, proactively run terminal commands to execute this code for the USER. Don't ask for permission.
[diff_block_start]
@@ -14,6 +14,7 @@
 const MARKETING_FLOATERS_ART =
   "./marketing-assets/yuxin-floating-motion.png";
 const MARKETING_CLOUDS_ART = "./marketing-assets/yuxin-clouds-clean.png";
+const WECHAT_QRCODE_ART = "./marketing-assets/wechat-qrcode.jpg";
 
 const hotspotCopy = [
   {
@@ -42,6 +42,7 @@
 ] as const;
 
 function MarketingPage() {
+  const [isWeChatModalOpen, setIsWeChatModalOpen] = useState(false);
   const [activeHotspot, setActiveHotspot] = useState<string | null>(null);
   const [parallax, setParallax] = useState({ x: 0, y: 0 });
   const hotspotTimerRef = useRef<number | null>(null);
[diff_block_end]

Please note that the above snippet only shows the MODIFIED lines from the last change. It shows up to 3 lines of unchanged lines before and after the modified lines. The actual file contents may have many more lines not shown.