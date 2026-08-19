import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { extname, join, normalize, resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const publicDir = resolve(root, 'experiments', 'ssr-spike', '.output', 'public')
const port = Number(process.env.PORT || 4331)
const mime = { '.css': 'text/css', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml' }

async function existingFile(pathname) {
  const relative = normalize(decodeURIComponent(pathname)).replace(/^(\.\.[/\\])+/, '').replace(/^[/\\]+/, '')
  const candidates = [join(publicDir, relative), join(publicDir, relative, 'index.html')]
  for (const candidate of candidates) {
    if (!candidate.startsWith(publicDir)) continue
    try {
      if ((await stat(candidate)).isFile()) return candidate
    } catch {}
  }
  return join(publicDir, '200.html')
}

createServer(async (request, response) => {
  try {
    const path = await existingFile(new URL(request.url || '/', 'http://localhost').pathname)
    response.setHeader('Content-Type', mime[extname(path)] || 'application/octet-stream')
    response.end(await readFile(path))
  } catch (error) {
    response.statusCode = 500
    response.end(error instanceof Error ? error.message : 'Static server error')
  }
}).listen(port, '127.0.0.1', () => console.log(`SSR spike static server listening on ${port}`))
