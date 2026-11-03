import { createServer, request } from "node:http"
import { BlockList, createConnection, isIP } from "node:net"
import { z } from "zod"

const privateNetworks = new BlockList()
for (const [address, prefix] of [
  ["0.0.0.0", 8],
  ["10.0.0.0", 8],
  ["100.64.0.0", 10],
  ["127.0.0.0", 8],
  ["169.254.0.0", 16],
  ["172.16.0.0", 12],
  ["192.168.0.0", 16],
  ["192.0.0.0", 24],
  ["192.0.2.0", 24],
  ["198.18.0.0", 15],
  ["198.51.100.0", 24],
  ["203.0.113.0", 24],
  ["224.0.0.0", 3],
] as const)
  privateNetworks.addSubnet(address, prefix, "ipv4")

export function publicAddress(address: string): boolean {
  return isIP(address) === 4 && !privateNetworks.check(address, "ipv4")
}

export function allowedTarget(target: URL, controller: URL, hosts: readonly string[]): boolean {
  if (target.username || target.password) return false
  if (target.origin === controller.origin) return true
  if (target.protocol !== "https:" || (target.port && target.port !== "443")) return false
  return hosts.some((host) =>
    host.startsWith("*.")
      ? target.hostname.endsWith(host.slice(1)) && target.hostname !== host.slice(2)
      : target.hostname === host,
  )
}

export function startEgress(controller: URL, hosts: readonly string[], port = 3128) {
  const destination = async (target: URL) => {
    if (!allowedTarget(target, controller, hosts)) throw new Error("Destination is not allowed")
    const addresses = await Bun.dns.lookup(target.hostname, { family: 4 })
    if (!addresses.length) throw new Error("Destination did not resolve")
    if (target.origin !== controller.origin && addresses.some(({ address }) => !publicAddress(address)))
      throw new Error("Private destinations are not allowed")
    return { host: addresses[0].address, port: Number(target.port || (target.protocol === "https:" ? 443 : 80)) }
  }
  const server = createServer({ maxHeaderSize: 16 * 1024 }, async (incoming, response) => {
    try {
      const target = new URL(incoming.url || "")
      if (target.protocol !== "http:") throw new Error("HTTPS requires CONNECT")
      const remote = request(
        {
          ...(await destination(target)),
          method: incoming.method,
          path: `${target.pathname}${target.search}`,
          headers: { ...incoming.headers, host: target.host, connection: "close" },
          timeout: 30000,
        },
        (received) => {
          response.writeHead(received.statusCode || 502, received.headers)
          received.pipe(response)
        },
      )
      remote.on("error", () => response.destroy())
      remote.on("timeout", () => remote.destroy())
      response.on("close", () => remote.destroy())
      incoming.pipe(remote)
    } catch {
      response.writeHead(403).end()
    }
  })
  server.on("connect", async (incoming, client, head) => {
    try {
      const target = new URL(`https://${incoming.url}/`)
      const remote = createConnection({ ...(await destination(target)), timeout: 30000 })
      client.on("error", () => remote.destroy())
      client.on("close", () => remote.destroy())
      remote.on("error", () => client.destroy())
      remote.on("timeout", () => remote.destroy())
      remote.on("close", () => client.end())
      remote.once("connect", () => {
        client.write("HTTP/1.1 200 Connection Established\r\n\r\n")
        remote.write(head)
        client.pipe(remote).pipe(client)
      })
    } catch {
      client.end("HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
    }
  })
  server.timeout = 30000
  return server.listen(port, "0.0.0.0")
}

if (import.meta.main) {
  const controller = new URL(z.url().parse(Bun.env.GITEDGE_CONTROLLER))
  const hosts = z.array(z.string()).parse(JSON.parse(Bun.env.GITEDGE_EGRESS_HOSTS || "[]"))
  startEgress(controller, hosts)
}
