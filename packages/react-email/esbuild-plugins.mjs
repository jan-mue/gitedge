import { createRequire } from "node:module"

const require = createRequire(import.meta.resolve("react-email"))

export default [
  {
    name: "resolve-email-css-tree",
    setup(build) {
      // The CLI externalizes css-tree, so resolve it from its owning package
      // rather than from the backend directory where templates are rendered.
      build.onResolve({ filter: /^css-tree(?:\/|$)/ }, ({ path }) => ({
        path: require.resolve(path),
        external: true,
      }))
    },
  },
]
