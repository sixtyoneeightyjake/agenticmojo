/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        arcade: ['"Press Start 2P"', 'cursive'],
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      colors: {
        arcade: {
          blue: "#0b1d3a",
          navy: "#0f172a",
          gold: "#f59e0b",
          red: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};

