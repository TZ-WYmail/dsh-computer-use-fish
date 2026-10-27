import { normalizeMcp } from './cua.js'

const INPUT_TOOLS = new Set(['type_text', 'press_key', 'hotkey', 'click', 'double_click', 'right_click', 'scroll', 'drag'])
const NO_EFFECT = new Set([undefined, 'none', 'refused', 'rejected', 'not_applied'])

export { driverFailure } from './driver-errors.js'

const refused = (code, reason) => ({ effect: 'refused', code, reason })

export async function dispatchInput(call, tool, payload, options = {}) {
  const { approval, agent, toolName, signal, validateTarget, onState } = options
  if (signal?.aborted) return refused('operation_cancelled', '操作已取消。')
  const invoke = async (args) => {
    try {
      const execute = async contact => {
        if (signal?.aborted) return refused('operation_cancelled', '操作已取消。')
        if (options.presentInput && validateTarget) await validateTarget()
        if (signal?.aborted) return refused('operation_cancelled', '操作已取消。')
        contact?.()
        try { return normalizeMcp(await call(tool, args)) }
        catch (error) { if (error.driverResult) return normalizeMcp(error.driverResult); throw error }
      }
      return options.presentInput ? await options.presentInput(execute) : await execute()
    }
    catch (error) {
      if (error.driverResult) return normalizeMcp(error.driverResult)
      throw error
    }
  }
  const value = await invoke(payload)
  // A recommendation alone never proves that a partial input did not happen.
  if (!INPUT_TOOLS.has(tool) || value?.code !== 'background_unavailable' || !NO_EFFECT.has(value.effect)) return value
  if (!approval || !agent) return refused('foreground_approval_required', '后台输入不可用；需要本次前台操作批准。')
  onState?.('approval')
  let outcome
  try {
    outcome = await approval.request({ agent, toolName,
      reason: '后台输入不可用。仅本次改用前台可能切换窗口焦点并执行输入，是否批准？', signal })
  } catch { outcome = 'unavailable' }
  if (outcome !== 'allowed-once' || signal?.aborted) {
    return refused('foreground_approval_denied', `本次前台操作未获批准或已取消（${outcome}）。`)
  }
  if (!validateTarget) return refused('foreground_target_unverified', '没有目标复核器，已停止前台重试。')
  try { await validateTarget() }
  catch (error) { return refused('foreground_target_changed', error.message) }
  if (signal?.aborted) return refused('operation_cancelled', '操作已取消。')
  onState?.('executing')
  // Exactly one foreground dispatch; ambiguous results are never replayed.
  return invoke({ ...payload, delivery_mode: 'foreground' })
}

export function actionResult(label, value) {
  const failure = value && typeof value === 'object' &&
    (['refused', 'rejected', 'suspected_noop', 'none'].includes(value.effect) || value.code === 'background_unavailable' || value.error)
  if (failure) return { ok: false, status: 'failed', result: `${label}被引擎拒绝：${value.effect || ''} (${value.code || ''}) ${value.reason || value.error || value.escalation?.reason || ''}` }
  const confirmed = value?.effect === 'confirmed'
  return { ok: true, status: confirmed ? 'confirmed' : 'pending',
    result: `${label}${confirmed ? '完成（已确认）' : '已发送，结果待确认'}：${typeof value === 'string' ? value : JSON.stringify(value)}` }
}
