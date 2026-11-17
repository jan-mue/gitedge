/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string
  readonly VITE_SENTRY_DSN?: string
  readonly VITE_SENTRY_SAMPLE_RATE?: string
  readonly VITE_SIGNUPS_ENABLED?: string
  readonly VITE_VERCEL_ENV?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
