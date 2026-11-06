/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0a0a",
        panel: "#0f0f0f",
        panel2: "#171717",
        border: "#262626",
        ink: "#f3f2f2",
        muted: "#a3a3a3",
        faint: "#6d6d6d",
        accent: "#f5f0e6",
        good: "#7ad99c",
        bad: "#ff7a70",
        warn: "#e6c877",
        vio: "#b7a6f7",
        cy: "#7bd3e0",
      },
      fontFamily: {
        display: ["Geist", "Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        sans: ["Geist", "Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      maxWidth: {
        page: "1500px",
      },
    },
  },
  plugins: [],
};
