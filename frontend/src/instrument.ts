import * as Sentry from "@sentry/react"
import type { AnyRouter } from "@tanstack/react-router"

export function initSentry(router: AnyRouter): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return

  const apiUrl = import.meta.env.VITE_API_URL
  const tracesSampleRate = Number(import.meta.env.VITE_SENTRY_SAMPLE_RATE ?? "1.0")

  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_VERCEL_ENV,
    integrations: [
      Sentry.tanstackRouterBrowserTracingIntegration(router),
      Sentry.consoleLoggingIntegration({ levels: ["log", "warn", "error"] }),
      Sentry.replayIntegration(),
    ],
    tracesSampleRate: Number.isFinite(tracesSampleRate) ? tracesSampleRate : 1.0,
    tracePropagationTargets: apiUrl ? [/^\//, apiUrl] : [/^\//],
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
  })
}
