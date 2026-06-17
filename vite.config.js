import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // relative base so it deploys cleanly to GitHub Pages or a subpath
  base: "./",
});
