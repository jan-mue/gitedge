import { create } from "storybook/theming"

// Storybook's manager runs outside the preview iframe, so its API needs concrete colors.
const palette = {
  canvas: "#101217",
  surface: "#191c23",
  elevated: "#222630",
  border: "#333947",
  text: "#e4e7ed",
  muted: "#a6afbe",
  brand: "#ff963f",
  link: "#71b4f6",
}
export const theme = create({
  base: "dark",
  brandTitle: "GitEdge · Design System",
  brandUrl: "https://github.com/jan-mue/gitedge",
  brandImage: "/storybook-brand.svg",
  brandTarget: "_blank",
  fontBase: '"Inter Variable", system-ui, sans-serif',
  fontCode: '"JetBrains Mono Variable", monospace',
  colorPrimary: palette.brand,
  colorSecondary: palette.link,
  appBg: palette.canvas,
  appContentBg: palette.surface,
  appPreviewBg: palette.canvas,
  appBorderColor: palette.border,
  appBorderRadius: 6,
  textColor: palette.text,
  textMutedColor: palette.muted,
  barTextColor: palette.muted,
  barSelectedColor: palette.link,
  barHoverColor: palette.text,
  barBg: palette.surface,
  inputBg: palette.elevated,
  inputBorder: palette.border,
  inputTextColor: palette.text,
  inputBorderRadius: 4,
})
