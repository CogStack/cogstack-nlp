/**
 * No-op stand-in for ``@mctee/enterprise`` when VITE_MCT_EE is not enabled.
 * Keeps OSS ``vite`` / ``vite build`` resolving the dynamic import in
 * ``enterprise.ts`` without requiring the private EE package.
 */
export {}
