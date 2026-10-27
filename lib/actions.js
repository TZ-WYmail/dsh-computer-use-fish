/**
 * actions.js —— 动作工具实现：点击 / 双击 / 右键 / 输入 / 按键 / 滚动 / 拖拽。
 *
 * 每个动作都基于 screen_observe 的快照：
 *  - element 编号模式 → 透传 element_token（引擎校验快照是否过期）
 *  - x/y 坐标模式 → 使用快照窗口的 window-local 像素坐标
 */
import { cuaCall, normalizeMcp, withSession } from './cua.js'
import { getSnapshot } from './snapshot.js'
import { dispatchInput, actionResult } from './input-dispatch.js'
import { isCompanionWindow } from './companion.js'
import { resolveToken, resolveWindow } from './snapshot.js'
import { humanClick, resolveClickTarget, screenPointOf, windowLocalOf } from './human.js'

/**
 * 构造一次"基于编号或坐标"的引擎调用参数。
 * 坐标语义：screen_observe 输出的元素坐标是屏幕 pt（cua-driver 0.19.3 的
 * frame 即屏幕坐标），引擎 click/scroll/drag 需要 window-local，故换算。
 * @returns {object} 传给 cua-driver 的参数字段
 */
function targetArgs(args, cfg, extra = {}) {
  const out = {}
  const snap = getSnapshot()
  if (args.element !== undefined && args.element !== null) {
    const { pid, token } = resolveToken(Number(args.element), cfg.ttlMs)
    out.pid = pid
    out.element_token = token
  } else if (args.x !== undefined || args.y !== undefined) {
    if (args.x === undefined || args.y === undefined) {
      throw new Error('坐标模式必须同时提供 x 和 y。')
    }
    const { pid, windowId } = resolveWindow(cfg.ttlMs)
    const local = windowLocalOf(Number(args.x), Number(args.y), snap)
    out.pid = pid
    out.window_id = windowId // 坐标点击需 window_id 定位目标窗口（避免多窗口歧义）
    out.x = local.x
    out.y = local.y
  } else {
    throw new Error('必须提供 element（观察编号）或 x/y 坐标。')
  }
  return withSession({ ...out, ...extra })
}

/** Recheck snapshot identity, age and geometry after an asynchronous approval. */
function inputOptions(cfg, options, payload) {
  const call = options.call || cuaCall
  const resolve = options.resolve || resolveWindow
  const snapshot = getSnapshot()
  return { ...options, validateTarget: options.validateTarget || (async () => {
    if (snapshot && getSnapshot() !== snapshot) throw new Error('观察目标已变化，请重新观察。')
    const target = resolve(cfg.ttlMs)
    if (target.pid !== payload.pid || (payload.window_id && target.windowId !== payload.window_id)) {
      throw new Error('目标窗口已变化。')
    }
    if (call === cuaCall) {
      const current = await cuaCall('list_windows', { on_screen_only: true })
      const window = current.windows?.find(w => w.pid === target.pid && w.window_id === target.windowId)
      if (!window) throw new Error('目标窗口已关闭或不可见。')
      const before = snapshot?.windowBounds
      const after = window.bounds
      if (before && after && ['x', 'y', 'width', 'height'].some(k => Number.isFinite(before[k]) && before[k] !== after[k])) {
        throw new Error('目标窗口位置或尺寸已变化，请重新观察。')
      }
    }
  }) }
}

async function sendInput(tool, payload, cfg, options) {
  return dispatchInput(options.call || cuaCall, tool, payload, inputOptions(cfg, options, payload))
}

/**
 * 真人点击：解析目标（编号或坐标）→ 光标滑行 → 像素级点击。
 * @returns {Promise<{ok:boolean, result:string}>}
 */
async function humanAction(label, args, cfg, extra = {}, options = {}) {
  let target
  const snap = getSnapshot()
  if (args.element !== undefined && args.element !== null) {
    target = resolveClickTarget(Number(args.element), cfg.ttlMs)
  } else if (args.x !== undefined && args.y !== undefined) {
    const { pid, windowId } = resolveWindow(cfg.ttlMs)
    const sx = Number(args.x)
    const sy = Number(args.y)
    const local = windowLocalOf(sx, sy, snap)
    target = {
      pid,
      windowId,
      x: local.x,
      y: local.y,
      // 光标滑行用同一坐标空间（窗口逻辑像素），与点击保持一致
      sx: local.x,
      sy: local.y,
    }
  } else {
    throw new Error('必须提供 element（观察编号）或 x/y 坐标。')
  }
  const value = await humanClick({ ...target, ...extra }, {
    skipGlide: true,
    dispatch: (tool, payload) => sendInput(tool, payload, cfg, { ...options, toolName: options.toolName || 'computer_click' }),
  })
  return actionResult(label, value)
}

/** computer_click —— 真人操作：光标滑行 + 像素点击 */
export async function click(args, cfg, options = {}) {
  const extra = {}
  if (args.count) extra.count = Number(args.count)
  return humanAction('点击', args, cfg, extra, options)
}

/** computer_double_click */
export async function doubleClick(args, cfg, options = {}) {
  return humanAction('双击', args, cfg, { count: 2 }, options)
}

/** computer_right_click */
export async function rightClick(args, cfg, options = {}) {
  return humanAction('右键点击', args, cfg, { button: 'right' }, options)
}

/** computer_type —— 文本输入（可指定元素，否则输入到前台应用当前焦点） */
export async function typeText(args, cfg, options = {}) {
  const { call = cuaCall, resolve = resolveWindow } = options
  if (!args.text) throw new Error('computer_type: 缺少 text 参数。')
  const payload = withSession({ text: String(args.text), delivery_mode: 'background' })
  if (args.element !== undefined && args.element !== null) {
    const { pid, token } = resolveToken(Number(args.element), cfg.ttlMs)
    payload.pid = pid
    payload.element_token = token
  } else {
    // 即使输入当前焦点，也必须绑定到新鲜观察快照的窗口，禁止盲发到 desktop scope。
    const { pid, windowId } = resolve(cfg.ttlMs)
    payload.pid = pid
    payload.window_id = windowId
  }
  const value = await sendInput('type_text', payload, cfg, { ...options, toolName: 'computer_type' })
  return actionResult('输入', value)
}

/** computer_key —— 按键 / 快捷键（如 return、cmd+c） */
export async function key(args, cfg, options = {}) {
  return dispatchKey(args, cfg, options)
}

/**
 * computer_key dispatch with optional dependencies for deterministic tests.
 * Bare keys stay on press_key for classic Win32; modifier combinations use
 * hotkey so UIA/XAML accelerators receive the event.
 */
export async function dispatchKey(args, cfg, options = {}) {
  const { call = cuaCall, resolve = resolveWindow, platform = process.platform } = options
  if (!args.key) throw new Error('computer_key: 缺少 key 参数。')
  const parts = String(args.key).toLowerCase().split('+').map((s) => s.trim())
  const MODS = new Set(['cmd', 'command', 'ctrl', 'control', 'option', 'alt', 'shift', 'fn'])
  const modifiers = parts.filter((p) => MODS.has(p)).map((p) => {
    if (p === 'command') return 'cmd'
    if (p === 'control') return 'ctrl'
    if (p === 'option') return 'alt'
    return p
  })
  const keyName = parts.filter((p) => !MODS.has(p))[0]
  if (!keyName) throw new Error('computer_key: 无法解析按键（示例: return / cmd+c / shift+tab）。')
  const isCombo = modifiers.length > 0
  // Both routes require a fresh snapshot and retain pid + window_id targeting.
  // 注：只传 pid 在多窗口应用（QQ 等）会歧义，必须带 window_id
  const { pid, windowId } = resolve(cfg.ttlMs)
  const target = { pid, window_id: windowId }
  const deliveryMode = platform === 'win32' ? { delivery_mode: 'background' } : {}
  const payload = withSession(isCombo
    ? { keys: [...modifiers, keyName], ...target, ...deliveryMode }
    : { key: keyName, ...target, ...deliveryMode })
  const tool = isCombo ? 'hotkey' : 'press_key'
  const value = await sendInput(tool, payload, cfg, { ...options, toolName: 'computer_key' })
  return actionResult('按键', value)
}

/** computer_scroll */
export async function scroll(args, cfg, options = {}) {
  const { call = cuaCall, resolve = resolveWindow } = options
  const dir = args.direction || 'down'
  if (!['up', 'down', 'left', 'right'].includes(dir)) {
    throw new Error('computer_scroll: direction 必须是 up/down/left/right。')
  }
  const payload = withSession({ direction: dir })
  if (args.amount) payload.amount = Number(args.amount)
  if (args.element !== undefined && args.element !== null) {
    const { pid, token } = resolveToken(Number(args.element), cfg.ttlMs)
    payload.pid = pid
    payload.element_token = token
  } else {
    const { pid, windowId } = resolve(cfg.ttlMs)
    payload.pid = pid
    payload.window_id = windowId
    if (args.x !== undefined || args.y !== undefined) {
      if (!Number.isFinite(args.x) || !Number.isFinite(args.y)) throw new Error('滚动锚点必须同时提供有效的 x 和 y。')
      const point = windowLocalOf(args.x, args.y, getSnapshot())
      payload.x = point.x; payload.y = point.y
    }
  }
  const value = await sendInput('scroll', payload, cfg, { ...options, toolName: 'computer_scroll' })
  return actionResult('滚动', value)
}

/** computer_drag —— 拖拽（坐标 = 窗口本地截图像素，与观察输出同空间） */
export async function drag(args, cfg, options = {}) {
  const { call = cuaCall, resolve = resolveWindow } = options
  const { pid, windowId } = resolve(cfg.ttlMs)
  if ([args.from_x, args.from_y, args.to_x, args.to_y].some((v) => v === undefined)) {
    throw new Error('computer_drag: 需要 from_x/from_y/to_x/to_y。')
  }
  const from = windowLocalOf(Number(args.from_x), Number(args.from_y), getSnapshot())
  const to = windowLocalOf(Number(args.to_x), Number(args.to_y), getSnapshot())
  const payload = withSession({
    pid,
    window_id: windowId,
    from_x: from.x,
    from_y: from.y,
    to_x: to.x,
    to_y: to.y,
  })
  if (args.duration_ms) payload.duration_ms = Number(args.duration_ms)
  const value = await sendInput('drag', payload, cfg, { ...options, toolName: 'computer_drag' })
  return actionResult('拖拽', value)
}

/** computer_wait —— 本地等待（不调引擎） */
export async function wait(args) {
  const ms = Math.max(0, Math.min(Number(args.ms) || 1000, 60000))
  await new Promise((r) => setTimeout(r, ms))
  return { ok: true, result: `已等待 ${ms}ms。` }
}

/** app_list —— 列出应用 */
export async function listApps({ call = cuaCall, platform = process.platform } = {}) {
  const value = await call('list_apps')
  let windows = []
  if (platform === 'linux') {
    try { windows = (await call('list_windows', {})).windows || [] } catch { /* Retain desktop metadata if window enumeration fails. */ }
  }
  const byPid = new Map()
  for (const w of windows) if (!isCompanionWindow(w)) byPid.set(w.pid, (byPid.get(w.pid) || 0) + 1)
  const apps = (value.apps || []).filter(a => a.running && !isCompanionWindow(a)
    && (platform !== 'linux' || byPid.has(a.pid) || a.windows?.length || a.kind === 'desktop' || a.bundle_id || a.launch_path || a.active))
  for (const w of windows) {
    if (!isCompanionWindow(w) && !apps.some(a => a.pid === w.pid)) {
      apps.push({ name: w.app_name || '应用', pid: w.pid, running: true })
    }
  }
  const lines = apps.map(a => {
    const count = byPid.get(a.pid) || a.windows?.length || 0
    return `- ${a.name || a.app_name || '应用'}${count ? ` (${count} 窗口)` : ''} [pid=${a.pid}]${a.active ? ' ★活动' : ''}`
  })
  return { ok: true, result: `正在运行的应用（${apps.length} 个）：\n${lines.join('\n')}`,
    apps: apps.map(a => ({ name: a.name || a.app_name || '应用', pid: a.pid, active: Boolean(a.active) })) }
}

/** app_launch —— 启动应用（后台），可选前置 */
export async function launchApp(args, { call = cuaCall, delay = ms => new Promise(r => setTimeout(r, ms)) } = {}) {
  if (!args.name && !args.bundle_id) {
    throw new Error('app_launch: 需要 name（应用名）或 bundle_id。')
  }
  const payload = {}
  if (args.bundle_id) payload.bundle_id = String(args.bundle_id)
  else payload.name = String(args.name)
  if (args.creates_new_instance) payload.creates_new_instance = true
  let launched
  try { launched = await call('launch_app', payload) }
  catch (error) {
    if (error.driverResult?.code !== 'launch_handoff_timeout' || args.creates_new_instance) throw error
    // Never relaunch after a handoff timeout: the original request may have worked.
    const wanted = String(args.bundle_id || args.name).toLowerCase()
    for (let attempt = 0; attempt < 4; attempt++) {
      const value = await call('list_apps', {})
      const app = value.apps?.find(a => a.running && [a.name, a.bundle_id, String(a.launch_path || '').split(/\s+/)[0].split('/').pop()]
        .some(name => String(name || '').toLowerCase() === wanted))
      if (app?.pid) {
        const windows = (await call('list_windows', {})).windows || []
        const visible = windows.some(w => w.pid === app.pid && w.is_on_screen !== false)
        return { ok: true, status: visible ? 'completed' : 'pending', pid: app.pid,
          result: `启动握手超时，但已确认应用进程运行${visible ? '且窗口可见；请观察界面确认就绪。' : '；窗口尚待确认。'}` }
      }
      if (attempt < 3) await delay(250)
    }
    throw error
  }

  // 若请求前置，找 pid 并 bring_to_front
  let pid = launched?.pid ?? null
  let frontNote = ''
  if (args.bring_to_front && pid) {
    await call('bring_to_front', { pid })
    frontNote = ' 已前置'
  }

  const detail = typeof launched === 'string' ? launched : JSON.stringify(launched)
  return {
    ok: true,
    result: `应用已启动${frontNote}：${detail}`,
    pid,
  }
}
