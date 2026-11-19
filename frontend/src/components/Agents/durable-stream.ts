/** Reconnect the AG-UI transport with an exclusive Redis stream cursor. */
export const durableAgentStream = (url: string, headers: HeadersInit, signal?: AbortSignal | null) => {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    async start(controller) {
      let cursor = "0-0"
      let failures = 0
      try {
        while (!signal?.aborted) {
          try {
            const response = await fetch(url, {
              headers: { ...Object.fromEntries(new Headers(headers)), "Last-Event-ID": cursor },
              signal,
            })
            if (!response.ok || !response.body) throw new Error(`Stream request failed (${response.status})`)
            const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
            let pending = ""
            try {
              while (true) {
                const { value, done } = await reader.read()
                if (done) break
                pending += value
                let boundary = pending.indexOf("\n\n")
                while (boundary >= 0) {
                  const frame = pending.slice(0, boundary)
                  pending = pending.slice(boundary + 2)
                  const position = /^id: (\d+-\d+)$/m.exec(frame)
                  const payload = /^data: (.+)$/m.exec(frame)
                  if (payload) {
                    const event = JSON.parse(payload[1])
                    controller.enqueue(encoder.encode(`${frame}\n\n`))
                    if (position) cursor = position[1]
                    failures = 0
                    if (event.type === "RUN_FINISHED" || event.type === "RUN_ERROR") {
                      controller.close()
                      return
                    }
                  }
                  boundary = pending.indexOf("\n\n")
                }
              }
            } finally {
              await reader.cancel()
              reader.releaseLock()
            }
          } catch (error) {
            if (signal?.aborted || ++failures > 5) throw error
          }
          await new Promise((resolve) => setTimeout(resolve, 300))
        }
        controller.close()
      } catch (error) {
        controller.error(error)
      }
    },
  })
  return Promise.resolve(new Response(body, { headers: { "Content-Type": "text/event-stream" } }))
}
