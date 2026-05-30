Created At: 2026-05-30T09:25:17Z
Completed At: 2026-05-30T09:25:17Z
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":3,"LineContent":"import MarketingPage from \"./MarketingPage\";"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":5,"LineContent":"  MARKETING_FILE_NAME,"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":6,"LineContent":"  MARKETING_ROUTE_PATH,"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":7,"LineContent":"  isMarketingRoute,"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":9,"LineContent":"} from \"./marketingContent\";"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":11,"LineContent":"describe(\"marketing homepage route\", () =\u003e {"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":12,"LineContent":"  test(\"only uses the marketing page on the standalone marketing path\", () =\u003e {"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":13,"LineContent":"    expect(MARKETING_ROUTE_PATH).toBe(\"/marketing\");"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":14,"LineContent":"    expect(isMarketingRoute(\"/marketing\")).toBe(true);"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":15,"LineContent":"    expect(isMarketingRoute(\"/marketing/\")).toBe(true);"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":16,"LineContent":"    expect(MARKETING_FILE_NAME).toBe(\"marketing.html\");"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.test.tsx","LineNumber":17,"LineContent":"    expect(isMarketingRoute(\"/dist/marketing.html\")).toBe(true);"}
{"File":"d:\\CodeWorkspace
<truncated 4323 bytes>
x","LineNumber":17,"LineContent":"const WECHAT_QRCODE_ART = \"./marketing-assets/wechat-qrcode.jpg\";"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":22,"LineContent":"    className: \"marketing-hotspot-cat\","}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":28,"LineContent":"    className: \"marketing-hotspot-earth\","}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":34,"LineContent":"    className: \"marketing-hotspot-ufo\","}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":40,"LineContent":"    className: \"marketing-hotspot-bunny\","}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":46,"LineContent":"function MarketingPage() {"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":57,"LineContent":"    window.location.pathname.toLowerCase().endsWith(MARKETING_FILE_NAME)"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":58,"LineContent":"      ? `./${MARKETING_FILE_NAME}`"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":59,"LineContent":"      : \"/marketing\";"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":115,"LineContent":"    \"--marketing-base-url\": `url(\"${MARKETING_BASE_ART}\")`,"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":116,"LineContent":"    \"--marketing-floaters-url\": `url(\"${MARKETING_FLOATERS_ART}\")`,"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":117,"LineContent":"    \"--marketing-clouds-url\": `url(\"${MARKETING_CLOUDS_ART}\")`,"}
{"File":"d:\\CodeWorkspace\\电脑桌宠\\src\\marketing\\MarketingPage.tsx","LineNumber":118,"LineContent":"    \"--marketing-floater-x\": `${parallax.x * 10}px`,"}
(...44 more results not shown)