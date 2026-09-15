/**
 * Load the MedCAT Trainer Enterprise frontend plugin when VITE_MCT_EE=1.
 *
 * Local dev: set MCT_EE_ROOT to the ``medcat-trainer-ee/frontend/src`` folder and
 * run the OSS frontend with ``VITE_MCT_EE=1 npm run dev``.
 */
export async function loadEnterprisePlugin(): Promise<void> {
  if (import.meta.env.VITE_MCT_EE !== '1') {
    return
  }
  try {
    await import('@mctee/enterprise')
    console.info('[Bootstrap] Enterprise plugin loaded')
  } catch (error) {
    console.warn('[Bootstrap] Enterprise plugin not loaded:', error)
  }
}
