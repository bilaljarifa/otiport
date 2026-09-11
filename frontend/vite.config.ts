import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Some Windows setups resolve "localhost" to 127.0.0.1 (IPv4) while
    // Vite's default dev server binds IPv6 loopback (::1) only, which then
    // refuses IPv4 connections (ERR_CONNECTION_REFUSED in the browser even
    // though the process is "running"). Binding explicitly to 0.0.0.0 makes
    // it listen on IPv4 too, alongside IPv6.
    host: '0.0.0.0',
  },
})
