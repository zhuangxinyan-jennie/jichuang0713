/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["Nunito", "Varela Round", "ui-rounded", "system-ui", "sans-serif"],
      },
      colors: {
        forest: { DEFAULT: "#1e6b4a", light: "#2d8f68", deep: "#134d36" },
        honey: { DEFAULT: "#f4c430", light: "#fce38a" },
        sky: { DEFAULT: "#5ab4e5", light: "#a8dff7" },
        cream: { DEFAULT: "#fffcf5" },
      },
    },
  },
  plugins: [],
};
