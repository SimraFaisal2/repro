/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0d1117",
        panel: "#161b22",
        panel2: "#1c2128",
        border: "#30363d",
        ink: "#e6edf3",
        muted: "#8b949e",
        faint: "#6e7681",
        accent: "#58a6ff",
        good: "#3fb950",
        bad: "#f85149",
        warn: "#d29922",
        vio: "#bc8cff",
        cy: "#39c5cf",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
};
