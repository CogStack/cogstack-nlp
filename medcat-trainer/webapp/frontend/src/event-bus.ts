// eventBus.js
import emitter from 'tiny-emitter/instance'

export default {
    $on: (...args: any[]) => emitter.on(...args),
    $off: (...args: any[]) => emitter.off(...args),
    $emit: (...args: any[]) => emitter.emit(...args)
}
