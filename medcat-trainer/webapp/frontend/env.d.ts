/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, any>
  export default component
}

declare module 'tiny-emitter/instance' {
  export interface TinyEmitterInstance {
    on(event: string, callback: (...args: unknown[]) => void, ctx?: unknown): TinyEmitterInstance
    off(event: string, callback?: (...args: unknown[]) => void): TinyEmitterInstance
    emit(event: string, ...args: any[]): TinyEmitterInstance
  }
  const emitter: TinyEmitterInstance
  export default emitter
}
