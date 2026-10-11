import type { VercelConfig } from "@vercel/config/v1"

const frontendConfig: VercelConfig = {
  relatedProjects: ["prj_Mo9JYgDx7MXkiPmHscPQgLpH3JN6"],
  rewrites: [
    { source: "/:owner/:repo.git/:path*", destination: "https://gitedge-backend.vercel.app/:owner/:repo.git/:path*" },
    { source: "/(.*)", destination: "/index.html" },
  ],
  git: { deploymentEnabled: { "renovate/*": false } },
}
const storybookConfig: VercelConfig = {
  framework: null,
  buildCommand: "bun run build-storybook",
  outputDirectory: "storybook-static",
  git: { deploymentEnabled: { "renovate/*": false } },
}
export const config: VercelConfig = process.env.DEPLOY_TARGET === "storybook" ? storybookConfig : frontendConfig
