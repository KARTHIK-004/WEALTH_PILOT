import { demoAllowed } from "@/lib/demo-mode"

/** Whether THIS build honours `?demo=true` on the Financial Behaviour page: a Vite development server, or a build made with `VITE_DEMO_MODE=true`. A production build leaves both unset, so the query is ignored. This is the only place the demo switch reads the build environment; it is not a sentiment or model flag. */
export const DEMO_MODE_ALLOWED: boolean = demoAllowed({ DEV: import.meta.env.DEV, VITE_DEMO_MODE: import.meta.env.VITE_DEMO_MODE })
