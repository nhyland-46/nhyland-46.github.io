/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // map palette — muted, flat, no country labels
        ocean: "#dce6ef",
        land: "#f4f1ea",
        landline: "#d9d2c5",
        birth: "#22c55e", // green marker
        death: "#ef4444", // red marker
      },
    },
  },
  plugins: [],
};
