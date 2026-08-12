import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),

  {
    // The flow tests read raw JSON straight off the wire and assert on the
    // field names it actually contains. Typing those responses would defeat
    // the exercise: the assertions would then be checking a type we wrote
    // rather than what the server sent, which is the one thing they exist to
    // catch. So `any` is the right type here, and only here.
    files: ["tests/flows.test.ts"],
    rules: { "@typescript-eslint/no-explicit-any": "off" },
  },
]);

export default eslintConfig;
