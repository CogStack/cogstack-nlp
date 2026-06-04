import type { Component } from 'vue'
import type { AxiosInstance } from 'axios'
import type { RouteRecordRaw } from 'vue-router'

export interface MenuExtension {
  id: string
  label: string
  route?: string
  href?: string
  [key: string]: unknown
}

export interface PluginRouteDescriptor {
  path: string
  component: string
  name?: string
  [key: string]: unknown
}

/** Build-time route with a resolved Vue component. */
export interface PluginRouteRegistration {
  path: string
  name?: string
  component: Component
}

export interface PluginRegistration {
  routes?: PluginRouteRegistration[]
  menuItems?: MenuExtension[]
  slots?: Record<string, Component>
}

export interface BootstrapPayload {
  features: string[]
  menu_extensions: MenuExtension[]
  routes: PluginRouteDescriptor[]
}

const slotRegistry: Record<string, Component[]> = {}
const buildTimeMenuItems: MenuExtension[] = []
const buildTimeVueRoutes: RouteRecordRaw[] = []

let serverMenuExtensions: MenuExtension[] = []
let serverRoutes: PluginRouteDescriptor[] = []
let serverFeatures: string[] = []

/**
 * Register a build-time Vue plugin (e.g. @cogstack/mct-enterprise).
 * Call from the plugin package before the app mounts.
 */
export function registerPlugin(plugin: PluginRegistration): void {
  if (plugin.menuItems?.length) {
    buildTimeMenuItems.push(...plugin.menuItems)
  }
  if (plugin.routes?.length) {
    for (const route of plugin.routes) {
      buildTimeVueRoutes.push({
        path: route.path,
        name: route.name,
        component: route.component
      })
    }
  }
  if (plugin.slots) {
    for (const [slotName, component] of Object.entries(plugin.slots)) {
      if (!slotRegistry[slotName]) {
        slotRegistry[slotName] = []
      }
      slotRegistry[slotName].push(component)
    }
  }
}

export function getSlotComponents(slotName: string): Component[] {
  return slotRegistry[slotName] ? [...slotRegistry[slotName]] : []
}

export function getMenuItems(): MenuExtension[] {
  return [...buildTimeMenuItems, ...serverMenuExtensions]
}

export function getPluginVueRoutes(): RouteRecordRaw[] {
  return [...buildTimeVueRoutes]
}

export function getPluginRouteDescriptors(): PluginRouteDescriptor[] {
  return [...serverRoutes]
}

export function getEnabledFeatures(): string[] {
  return [...new Set(serverFeatures)]
}

export function hasFeature(feature: string): boolean {
  return serverFeatures.includes(feature)
}

/** Load server bootstrap payload (requires authentication). */
export async function loadBootstrap(http: AxiosInstance): Promise<BootstrapPayload | null> {
  try {
    const { data } = await http.get<BootstrapPayload>('/api/bootstrap/')
    serverMenuExtensions = data.menu_extensions ?? []
    serverRoutes = data.routes ?? []
    serverFeatures = data.features ?? []
    return data
  } catch {
    return null
  }
}

/** Reset registries (unit tests). */
export function clearPluginRegistry(): void {
  for (const key of Object.keys(slotRegistry)) {
    delete slotRegistry[key]
  }
  buildTimeMenuItems.length = 0
  buildTimeVueRoutes.length = 0
  serverMenuExtensions = []
  serverRoutes = []
  serverFeatures = []
}
