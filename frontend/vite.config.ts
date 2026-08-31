/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// El backend Django (URL en VITE_API_BASE_URL) es un servicio aparte; Vercel
// solo sirve estáticos (SDD-web §3.2).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
  },
});
