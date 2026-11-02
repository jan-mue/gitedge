import type { CommitFileChange, CompareResult } from "@/client"

const diffFile: CommitFileChange = {
  path: "src/config.py",
  change_type: "modify",
  additions: 1,
  deletions: 1,
  patch: "",
  language: "Python",
  hunks: [
    {
      header: "@@ -1,2 +1,2 @@",
      lines: [
        {
          kind: "delete",
          old_line: 1,
          new_line: null,
          tokens: [
            { text: "timeout", syntax: "name" },
            { text: " = ", syntax: "operator" },
            { text: "12", syntax: "literal-number", changed: true },
          ],
        },
        {
          kind: "add",
          old_line: null,
          new_line: 1,
          tokens: [
            { text: "timeout", syntax: "name" },
            { text: " = ", syntax: "operator" },
            { text: "42", syntax: "literal-number", changed: true },
          ],
        },
        {
          kind: "context",
          old_line: 2,
          new_line: 2,
          tokens: [
            { text: "print", syntax: "name-builtin" },
            { text: "(timeout)", syntax: "text" },
          ],
        },
      ],
      rows: [
        { old: 0, new: 1 },
        { old: 2, new: 2 },
      ],
    },
  ],
}

export const comparisonFixture: CompareResult = {
  base_commit: "a".repeat(40),
  head_commit: "b".repeat(40),
  files: [diffFile, { ...diffFile, path: "tests/test_config.py" }],
  additions: 2,
  deletions: 2,
}
