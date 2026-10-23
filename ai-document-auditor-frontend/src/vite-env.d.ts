/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Minimal shared-secret auth (see backend src/auth.py). Optional -- unset
  // matches the backend's own "no API_KEY configured" = auth disabled.
  readonly VITE_API_KEY?: string;
  // The backend's base URL. Optional -- unset falls back to the local dev
  // server (http://localhost:8000). Set for any production build.
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
