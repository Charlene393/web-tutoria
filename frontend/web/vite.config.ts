import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          three: ["three", "@react-three/fiber"],
          vrm: ["@pixiv/three-vrm"],
        },
      },
    },
  },
  server: {
    port: 5173,
  },
});
