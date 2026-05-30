with open("final_marketing.css", "r", encoding="utf-8") as f:
    content = f.read()

# Fix 1: Semicolon and closing brace for .marketing-stage-layer, .marketing-layer-parallax
old_style_1 = """.marketing-stage-layer,
.marketing-layer-parallax {
  position: absolute;
  inset: 0;
  pointer-events: none"""

new_style_1 = """.marketing-stage-layer,
.marketing-layer-parallax {
  position: absolute;
  inset: 0;
  pointer-events: none;
}"""

content = content.replace(old_style_1, new_style_1)

# Fix 2: Complete WeChat popover styles
old_style_2 = """/* Premium WeChat Dark Popover (similar to Image 2) */
.marketing-wechat-popover {
  position: absolute;
  top: 
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 10, 15, 0.45);
  backdrop-filter: blur(12px);
  opacity: 0;
  pointer-events: none;
  transition: opacity 300ms cubic-bezier(0.4, 0, 0.2, 1);
}"""

new_style_2 = """/* Premium WeChat Dark Popover (similar to Image 2) */
.marketing-wechat-popover {
  position: absolute;
  top: calc(100% + 12px);
  left: 50%;
  transform: translateX(-50%) translateY(8px) scale(0.94);
  width: 170px;
  background: rgba(30, 30, 34, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-radius: 16px;
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4);
  padding: 12px;
  box-sizing: border-box;
  opacity: 0;
  pointer-events: none;
  transition: opacity 220ms ease, transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1);
  z-index: 1000;
  backdrop-filter: blur(10px);
}

/* Upward pointing arrow in dark style */
.marketing-wechat-popover::before {
  content: "";
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(1px);
  border-width: 6px;
  border-style: solid;
  border-color: transparent transparent rgba(30, 30, 34, 0.96) transparent;
  z-index: 2;
}"""

content = content.replace(old_style_2, new_style_2)

# Fix 3: Upward arrow border
old_style_3 = """.marketing-modal-overlay.is-open .marketing-modal-content {
  transform: scale(1) translateY(0);
}

  transform: translateX(-50%);
  border-width: 7px;
  border-style: solid;
  border-color: transparent transparent rgba(255, 255, 255, 0.15) transparent;
  z-index: 1;
}"""

new_style_3 = """.marketing-modal-overlay.is-open .marketing-modal-content {
  transform: scale(1) translateY(0);
}

/* Subtle border for the arrow */
.marketing-wechat-popover::after {
  content: "";
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 7px;
  border-style: solid;
  border-color: transparent transparent rgba(255, 255, 255, 0.15) transparent;
  z-index: 1;
}"""

content = content.replace(old_style_3, new_style_3)

with open("final_marketing_clean.css", "w", encoding="utf-8") as out:
    out.write(content)

print("Successfully fixed and output to final_marketing_clean.css!")
