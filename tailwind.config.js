/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#18212f",
        paper: "#f7f8fb",
      },
      boxShadow: {
        soft: "0 18px 50px rgba(29, 39, 57, 0.10)",
      },
    },
  },
  plugins: [],
};
