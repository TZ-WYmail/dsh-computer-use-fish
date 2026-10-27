import net from 'node:net'
import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { mkdtempSync, chmodSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { getSnapshot } from './snapshot.js'
import { cuaCall, CUA_SESSION } from './cua.js'

const helperPids = new Set()
export const isCompanionWindow = window => helperPids.has(window.pid)

/** Geometry only. Text, labels, screenshots and typed values never cross IPC. */
export function presentationTarget(args = {}, snapshot = getSnapshot()) {
  const b = snapshot?.windowBounds
  if (!b || !['x', 'y', 'width', 'height'].every(k => Number.isFinite(b[k])) || b.width <= 0 || b.height <= 0) return null
  const bounds = Object.fromEntries(['x', 'y', 'width', 'height'].map(k => [k, b[k]]))
  let x = args.x ?? args.to_x, y = args.y ?? args.to_y
  if (args.element !== undefined) {
    const entry = snapshot.entries?.get(Number(args.element))
    x = entry?.x; y = entry?.y
  }
  const w = snapshot.screenshotWidth, h = snapshot.screenshotHeight
  const point = Number.isFinite(x) && Number.isFinite(y) && w > 0 && h > 0 && x >= 0 && y >= 0 && x < w && y < h
    ? { x: bounds.x + x / w * bounds.width, y: bounds.y + y / h * bounds.height } : null
  const fromPoint = Number.isFinite(args.from_x) && Number.isFinite(args.from_y) && w > 0 && h > 0 && args.from_x >= 0 && args.from_y >= 0 && args.from_x < w && args.from_y < h
    ? { x: bounds.x + args.from_x / w * bounds.width, y: bounds.y + args.from_y / h * bounds.height } : null
  return { bounds, point, fromPoint, coordinateSpace: 'driver' }
}

export function createCompanion({ enabled = false, launch = true, size = 300, reducedMotion = false, diagnosticsPath = null } = {}) {
  if (!enabled) return { publish() {}, close() {}, async withHidden(fn) { return fn() }, async perform(_event, invoke) { return invoke() }, setDisplay() {} }
  const dir = mkdtempSync(join(tmpdir(), `dsh-fish-${process.getuid?.() ?? 'user'}-`))
  chmodSync(dir, 0o700)
  const socketPath = join(dir, 'events.sock'), token = randomBytes(24).toString('hex')
  let userVisible = true
  let helper, closed = false, sequence = 0, display = null, lastError = '', exitCode = null
  let current = { type: 'state', state: 'idle', tool: '', actionId: '', seq: 0, target: null }
  const clients = new Set(), acknowledgements = new Map(), gestures = new Map()
  let cursorQueue = Promise.resolve()
  const cursor = enabled => {
    if (!launch) return
    cursorQueue = cursorQueue.then(() => cuaCall('set_agent_cursor_enabled', { session: CUA_SESSION, enabled })).catch(() => {})
    return cursorQueue
  }
  const send = (client, value) => {
    if (client.destroyed) return
    if (client.writableLength > 32768) return client.destroy()
    client.write(JSON.stringify(value) + '\n')
  }
  const broadcast = value => { for (const client of clients) send(client, value) }
  const server = net.createServer(client => {
    let authenticated = false, control = false, buffer = ''
    const timeout = setTimeout(() => { if (!authenticated) client.destroy() }, 2000).unref()
    client.on('error', () => {})
    client.on('close', () => { clearTimeout(timeout); clients.delete(client); if (!clients.size) { cursor(true); for (const resolve of gestures.values()) resolve(false) } })
    client.on('data', data => {
      buffer += data
      if (buffer.length > 4096) return client.destroy()
      while (buffer.includes('\n')) {
        const at = buffer.indexOf('\n'), line = buffer.slice(0, at); buffer = buffer.slice(at + 1)
        let value
        try { value = JSON.parse(line) } catch { return client.destroy() }
        if (!authenticated) {
          if (value.type !== 'hello' || value.token !== token) return client.destroy()
          authenticated = true; clearTimeout(timeout)
          control = value.role === 'control'
          if (control) { send(client, { type: 'status', visible: userVisible, connected: clients.size > 0, calibrated: Boolean(display?.mapping) }); continue }
          clients.add(client); send(client, current)
          if (!userVisible) send(client, { type: 'visibility', visible: false })
          // Calibrate the driver's desktop units against our own known GTK window.
          // A screenshot can be 2x while window bounds are already logical pixels.
          const geometry = value.geometry
          if (launch && helper?.pid && geometry && ['x', 'y', 'width', 'height'].every(k => Number.isFinite(geometry[k]))) {
            const calibrate = async () => {
              // GNOME may expose a newly mapped XWayland window after the first query.
              for (const delay of [0, 150, 350, 700]) {
                if (delay) await new Promise(resolve => setTimeout(resolve, delay))
                if (closed || client.destroyed) return
                const result = await cuaCall('list_windows', {}).catch(() => ({}))
                const window = result.windows?.find(w => w.pid === helper.pid && w.title === 'DSH Fat Fish Companion')
                const b = window?.bounds
                if (!b || geometry.width <= 0 || geometry.height <= 0) continue
                const sx = b.width / geometry.width, sy = b.height / geometry.height
                if (sx < .5 || sx > 4 || Math.abs(sx - sy) > .02 * sx) continue
                display = { ...display, mapping: { sx, sy, ox: b.x - geometry.x * sx, oy: b.y - geometry.y * sy } }
                current = { ...current, display, seq: ++sequence }; broadcast(current); cursor(!userVisible)
                return
              }
            }
            calibrate().catch(() => {})
          }
        } else if (control) {
          if (value.type !== 'control' || !['hide', 'show', 'status'].includes(value.command)) return client.destroy()
          if (value.command !== 'status') {
            userVisible = value.command === 'show'
            cursor(!userVisible || !display?.mapping)
            if (!userVisible) for (const resolve of gestures.values()) resolve(false)
            broadcast({ type: 'visibility', visible: userVisible })
          }
          send(client, { type: 'status', visible: userVisible, connected: clients.size > 0, calibrated: Boolean(display?.mapping) })
        } else if (value.type === 'gesture_ready' && typeof value.motionId === 'string') {
          gestures.get(value.motionId)?.(true)
        } else if (value.type === 'hidden' && typeof value.captureId === 'string') {
          acknowledgements.get(value.captureId)?.()
        }
        // Clients have no input execution or arbitrary event publishing endpoint.
      }
    })
  })
  const ready = new Promise(resolve => {
    server.on('error', () => resolve(false))
    server.listen(socketPath, () => {
      chmodSync(socketPath, 0o600)
      writeFileSync(join(dir, 'control.json'), JSON.stringify({ socket: socketPath, token, pid: process.pid }), { mode: 0o600 })
      resolve(true)
      if (!launch || closed) return
      helper = spawn('/usr/bin/python3', [join(dirname(fileURLToPath(import.meta.url)), '../companion/pet.py'),
        '--socket', socketPath, '--size', String(Math.max(200, Math.min(size, 420))), ...(reducedMotion ? ['--reduced-motion'] : []), ...(diagnosticsPath ? ['--diagnostics', diagnosticsPath] : [])], {
        env: { ...process.env, GDK_BACKEND: 'x11', NO_AT_BRIDGE: '1', DSH_FISH_TOKEN: token },
        stdio: ['ignore', 'ignore', 'pipe'],
      })
      if (helper.pid) helperPids.add(helper.pid)
      helper.stderr.on('data', data => { lastError = (lastError + data).slice(-2048) })
      helper.on('error', error => { lastError = error.message })
      helper.on('exit', code => { exitCode = code; helperPids.delete(helper.pid) })
    })
  })
  server.unref()
  return {
    ready, socketPath, token,
    get pid() { return helper?.pid },
    status() { return { connected: clients.size > 0, pid: helper?.pid, exitCode, calibrated: Boolean(display?.mapping), error: lastError } },
    setDisplay(value) {
      if (Number.isFinite(value?.width) && Number.isFinite(value?.height)) display = { ...display, width: value.width, height: value.height, ...(value.mapping && ['sx','sy','ox','oy'].every(k => Number.isFinite(value.mapping[k])) ? { mapping: value.mapping } : {}) }
    },
    publish({ state, tool = '', actionId = '', target = null }) {
      if (closed) return
      current = { type: 'state', state, tool, actionId, target, display, seq: ++sequence }
      broadcast(current)
    },
    async perform(event, invoke, signal) {
      if (closed || !clients.size || !userVisible || !display?.mapping || !event.target?.bounds) return invoke()
      const motionId = randomBytes(8).toString('hex')
      const count = event.tool === 'computer_double_click' ? 2 : Math.max(1, Math.min(3, event.count || 1))
      let timer, abort
      const ready = new Promise(resolve => {
        gestures.set(motionId, resolve)
        timer = setTimeout(() => resolve(false), 2100)
        abort = () => resolve(false)
        signal?.addEventListener('abort', abort, { once: true })
        if (signal?.aborted) resolve(false)
      })
      broadcast({ type: 'gesture', phase: 'approach', motionId, actionId: typeof event.actionId === 'string' ? event.actionId.slice(0,80) : motionId, tool: event.tool, target: event.target, display, count, direction: ['up','down','left','right'].includes(event.direction) ? event.direction : 'down', durationMs: Math.max(150, Math.min(1500, event.durationMs || 500)) })
      try {
        const arrived = await ready
        if (signal?.aborted) throw new Error('操作已取消。')
        if (!arrived) { cursor(true); broadcast({ type: 'gesture', phase: 'cancel', motionId }); return await invoke() }
        await cursor(!event.target.point)
        // The renderer is at the contact pose. Desktop input still belongs only to the host.
        const value = await invoke(() => broadcast({ type: 'gesture', phase: 'dispatch', motionId }))
        // Linux pointer actions reveal the native overlay again; hide it after dispatch too.
        await cursor(!userVisible || !clients.size || !event.target.point)
        const refused = ['refused','rejected','none','suspected_noop'].includes(value?.effect) || value?.code === 'background_unavailable' || value?.error
        broadcast({ type: 'gesture', phase: refused ? 'cancel' : 'settle', motionId })
        return value
      } catch (error) {
        broadcast({ type: 'gesture', phase: 'cancel', motionId }); throw error
      } finally {
        clearTimeout(timer); gestures.delete(motionId); signal?.removeEventListener('abort', abort)
      }
    },
    async withHidden(fn) {
      if (!clients.size || closed) return fn()
      const captureId = randomBytes(8).toString('hex')
      let timer
      const hidden = new Promise(resolve => {
        acknowledgements.set(captureId, () => resolve(true))
        timer = setTimeout(() => resolve(false), 1200)
      })
      broadcast({ type: 'visibility', visible: false, captureId })
      try {
        if (!await hidden) {
          helper?.kill('SIGTERM')
          for (const client of clients) client.destroy()
          await new Promise(resolve => setTimeout(resolve, 100))
        }
        return await fn()
      } finally {
        clearTimeout(timer); acknowledgements.delete(captureId)
        broadcast({ type: 'visibility', visible: userVisible })
      }
    },
    close() {
      if (closed) return
      closed = true; cursor(true); helper?.kill('SIGTERM')
      for (const resolve of gestures.values()) resolve(false)
      for (const client of clients) client.destroy()
      for (const resolve of acknowledgements.values()) resolve()
      acknowledgements.clear()
      server.close(() => rmSync(dir, { recursive: true, force: true }))
    },
  }
}
