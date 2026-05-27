import type { AxiosInstance } from 'axios'
import { loadBootstrap } from './registry'

/** Fetch ``GET /api/bootstrap/`` when the user may be authenticated. */
export async function initPluginBootstrap(http: AxiosInstance): Promise<void> {
  await loadBootstrap(http)
}
