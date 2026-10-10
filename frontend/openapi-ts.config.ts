import { defineConfig } from "@hey-api/openapi-ts"

export default defineConfig({
  input: "./openapi.json",
  output: "./src/client",

  plugins: [
    { name: "@hey-api/client-fetch", throwOnError: true },
    { name: "@hey-api/typescript", case: "preserve" },
    {
      name: "@hey-api/sdk",
      operations: {
        // NOTE: this doesn't allow tree-shaking
        strategy: "byTags",
        methods: "static",
        containerName: "{{name}}Service",
        methodName: (name: string): string => name.replace(/^[^-]*-/, ""),
      },
    },
    {
      name: "@tanstack/react-query",
      queryOptions: true,
      queryKeys: true,
      mutationOptions: true,
    },
  ],
})
