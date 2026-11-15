/** Shared by the server layout and the client theme store; must stay free of "use client". */
export const THEME_STORAGE_KEY = "stellaris-theme";

/**
 * Inlined in <head> by app/layout.tsx so a stored choice applies before first paint.
 * Absent or invalid values leave [data-theme] unset, which follows the OS setting.
 */
export const THEME_INIT_SCRIPT = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
