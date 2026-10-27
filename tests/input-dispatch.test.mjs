import test from 'node:test'
import assert from 'node:assert/strict'
import { dispatchInput, driverFailure, actionResult } from '../lib/input-dispatch.js'
import { click, doubleClick, rightClick, scroll, drag, dispatchKey } from '../lib/actions.js'
import { setSnapshot, clearSnapshot } from '../lib/snapshot.js'

const blocked = { effect: 'refused', code: 'background_unavailable' }
const confirmed = { effect: 'confirmed' }
const target = { pid: 42, window_id: 7 }
const approved = { agent: {}, approval: { request: async () => 'allowed-once' }, validateTarget: async () => {} }

for (const tool of ['type_text', 'press_key', 'hotkey', 'click', 'double_click', 'right_click', 'scroll', 'drag']) {
  test(`${tool}: exact one-shot foreground retry follows approval and target check`, async () => {
    const order = []
    const result = await dispatchInput(async (name, args) => {
      order.push(args.delivery_mode || 'background')
      return args.delivery_mode === 'foreground' ? confirmed : blocked
    }, tool, target, { ...approved,
      approval: { request: async () => { order.push('approval'); return 'allowed-once' } },
      validateTarget: async () => { order.push('validate') },
    })
    assert.equal(result.effect, 'confirmed')
    assert.deepEqual(order, ['background', 'approval', 'validate', 'foreground'])
  })
}

test('nonzero CLI exit retains structured refusal for approval', async () => {
  const error = new Error('CLI exit 1')
  error.driverResult = driverFailure('', 'warning\n{"code":"background_unavailable","effect":"none"}')
  let calls = 0
  const value = await dispatchInput(async () => { if (++calls === 1) throw error; return confirmed }, 'press_key', target, approved)
  assert.equal(calls, 2)
  assert.equal(value.effect, 'confirmed')
})

for (const effect of ['unverifiable', 'suspected_noop', 'partial', 'confirmed']) {
  test(`uncertain or applied ${effect} is never replayed, even with background_unavailable`, async () => {
    let calls = 0, asks = 0
    await dispatchInput(async () => { calls++; return { code: 'background_unavailable', effect } }, 'drag', target,
      { ...approved, approval: { request: async () => { asks++; return 'allowed-once' } } })
    assert.equal(calls, 1); assert.equal(asks, 0)
  })
}

test('a recommendation without explicit refusal does not cause input replay', async () => {
  let calls = 0
  await dispatchInput(async () => { calls++; return { escalation: { recommended: 'foreground' } } }, 'drag', target, approved)
  assert.equal(calls, 1)
})

test('denied approval cannot invoke foreground', async () => {
  let calls = 0
  const v = await dispatchInput(async () => { calls++; return blocked }, 'click', target,
    { ...approved, approval: { request: async () => 'denied' } })
  assert.equal(calls, 1); assert.equal(v.code, 'foreground_approval_denied')
})

test('a moved, closed or expired target aborts after approval', async () => {
  let calls = 0
  const v = await dispatchInput(async () => { calls++; return blocked }, 'press_key', target,
    { ...approved, validateTarget: async () => { throw Error('target moved') } })
  assert.equal(calls, 1); assert.equal(v.code, 'foreground_target_changed')
})

test('cancellation during target validation prevents the last dispatch', async () => {
  const controller = new AbortController(); let calls = 0
  const v = await dispatchInput(async () => { calls++; return blocked }, 'press_key', target,
    { ...approved, signal: controller.signal, validateTarget: async () => controller.abort() })
  assert.equal(calls, 1); assert.equal(v.code, 'operation_cancelled')
})

test('ordinary timeout exceptions never initiate a foreground retry', async () => {
  await assert.rejects(dispatchInput(async () => { throw Error('timeout') }, 'drag', target, approved), /timeout/)
})

test('unverified sends stay pending and cannot be described as confirmed success', () => {
  const r = actionResult('点击', { effect: 'unverifiable' })
  assert.equal(r.status, 'pending'); assert.match(r.result, /待确认/)
  assert.doesNotMatch(r.result, /完成/)
})

for (const [name, fn, args] of [
  ['click', click, { x: 5, y: 6 }], ['double', doubleClick, { x: 5, y: 6 }],
  ['right', rightClick, { x: 5, y: 6 }], ['scroll', scroll, { direction: 'down' }],
  ['drag', drag, { from_x: 2, from_y: 3, to_x: 5, to_y: 6 }],
  ['key', dispatchKey, { key: 'ctrl+a' }],
]) {
  test(`${name} action really passes through the shared dispatcher on Linux`, async () => {
    setSnapshot({ at: Date.now(), pid: 42, windowId: 7, entries: new Map() })
    const calls = []
    try {
      const result = await fn(args, { ttlMs: 30000 }, { ...approved, platform: 'linux',
        call: async (tool, payload) => { calls.push(payload); return calls.length === 1 ? blocked : confirmed } })
      assert.equal(result.ok, true)
      assert.equal(calls.length, 2)
      assert.equal(calls[1].delivery_mode, 'foreground')
      assert.equal(calls[1].pid, 42)
    } finally { clearSnapshot() }
  })
}

test('snapshot replacement while approval is open stops the action-level retry', async () => {
  setSnapshot({ at: Date.now(), pid: 42, windowId: 7, entries: new Map() })
  let calls = 0
  const r = await dispatchKey({ key: 'escape' }, { ttlMs: 30000 }, {
    agent: {}, approval: { request: async () => {
      setSnapshot({ at: Date.now(), pid: 43, windowId: 8, entries: new Map() }); return 'allowed-once'
    } }, call: async () => { calls++; return blocked },
  })
  clearSnapshot();assert.equal(calls, 1);assert.equal(r.ok, false)
})
