// eventBus.js
import emitter from 'tiny-emitter/instance'

export default {
  $on: (event: string, callback: (...args: unknown[]) => void, ctx?: unknown) =>
    emitter.on(event, callback, ctx),
  $off: (event: string, callback?: (...args: unknown[]) => void) => emitter.off(event, callback),
  $emit: (event: string, ...args: unknown[]) => emitter.emit(event, ...args)
}
