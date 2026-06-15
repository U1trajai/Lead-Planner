# Tool and skill reference

A field-level reference for every tool you can call. **Each call must include all fields marked `required`** — a missing required field makes the call fail. The examples below show a complete, valid call with every required field filled in; copy their shape. Field types: `string`, `number`, `integer`, `boolean`, `array`, `object`. "optional" fields may be omitted entirely — when omitting one, leave it out; never send the literal string `"null"` or `"undefined"`.

---

## bash — run a shell command
Use for running tests, git, build/install steps, read-only exploration, and invoking little-coder.

- `command` — string, **required**. The command to execute.
- `description` — string, **required**. What the command does, in 5–10 words.
- `timeout` — integer, optional. Timeout in **milliseconds**.
- `workdir` — string, optional. Directory to run in; use this instead of a `cd` command.

```json
{ "command": "npm install", "description": "Install project dependencies" }
```

Never omit `description` — it is required and the call fails without it. Never print a command as plain text instead of running it.

---

## read — read one file (read-only)
- `filePath` — string, **required**. Absolute path to the file or directory.
- `offset` — integer, optional. Line to start from (1-indexed).
- `limit` — integer, optional. Max lines to read (default 2000).

```json
{ "filePath": "/home/me/project/src/server.ts", "offset": 1, "limit": 200 }
```

---

## grep — search file contents by regex (read-only)
- `pattern` — string, **required**. The regular expression to search for.
- `path` — string, optional. Directory to search in (defaults to the working directory).
- `include` — string, optional. File glob to limit the search, e.g. `"*.ts"` or `"*.{ts,tsx}"`.

```json
{ "pattern": "function handleLogin", "include": "*.ts" }
```

---

## glob — find files by name pattern (read-only)
- `pattern` — string, **required**. Glob to match, e.g. `"**/*.ts"` or `"src/**/*.test.js"`.
- `path` — string, optional. Directory to search in. **Omit this field entirely** to use the working directory — do not pass `"null"` or `"undefined"`.

```json
{ "pattern": "**/*.test.ts" }
```

---

## question — ask the user
Use only for genuine ambiguity you could not resolve by exploring first (see the **intent-extraction** skill).

- `questions` — array, **required**. One or more question objects, each with:
    - `question` — string, **required**. The complete question text.
    - `header` — string, **required**. A very short label, **max 30 characters**.
    - `options` — array, **required**. Each option is an **object**, not a string:
        - `label` — string, **required**. The choice, 1–5 words.
        - `description` — string, **required**. A short explanation of the choice.
    - `multiple` — boolean, optional. Allow selecting more than one option.

```json
{
  "questions": [
    {
      "header": "Target runtime",
      "question": "Which runtime should this service target?",
      "options": [
        { "label": "Node.js", "description": "Run on the Node 20 LTS runtime" },
        { "label": "Deno", "description": "Run on the Deno runtime" }
      ],
      "multiple": false
    }
  ]
}
```

The most common mistake is making `options` a list of strings. Each option must be an object with both `label` and `description`.

---

## skill — load detailed instructions on demand
Skills are `SKILL.md` files holding the full procedure for one phase of your work. You start a session seeing only each skill's **name and description**; the full instructions are not in context until you load them.

- `name` — string, **required**. The skill's name, exactly as listed in `available_skills`.

```json
{ "name": "intent-extraction" }
```

When you reach a phase, call `skill` with its name to load the full `SKILL.md`, then follow it. **Reload the skill each time you enter its phase** rather than recalling it from an earlier turn — keeping detail out of context until needed is the point, so your instructions stay current.

Skills available to you and when to load each:
- `intent-extraction` — at the start of a request, to gather context and clear ambiguity before planning.
- `planning-artifacts` — once intent is clear, to write user stories / design doc / todo list / work breakdown.
- `delegating-to-little-coder` — before issuing any little-coder command, to construct it correctly.
- `reviewing-and-fixing` — after a little-coder command returns, to run tests, review output, and re-delegate fixes.

---

## File-modifying tools — you delegate these, you do not call them
opencode exposes `edit`, `write`, and `apply_patch`, which change file contents. Authoring or changing code and test files is implementation, which you always delegate to little-coder (run via `bash`) — never call these yourself. If you reach for one on a code or test file, stop and delegate instead. Their schemas are listed for reference only.

**edit** — replace exact text in a file:
- `filePath` — string, **required**. Absolute path.
- `oldString` — string, **required**. Text to replace.
- `newString` — string, **required**. Replacement text (must differ from `oldString`).
- `replaceAll` — boolean, optional. Replace every occurrence (default false).

**write** — create or overwrite a file:
- `content` — string, **required**. Full file contents.
- `filePath` — string, **required**. Absolute path.

**apply_patch** — apply a patch:
- `patchText` — string, **required**. The full patch text describing all changes.

---

## Other tools
**webfetch** — fetch the content of a URL:
- `url` — string, **required**.
- `format` — string, optional. One of `text`, `markdown`, `html` (default `markdown`).
- `timeout` — number, optional. Seconds, max 120.

```json
{ "url": "https://opencode.ai/docs/skills/", "format": "markdown" }
```

**websearch** — search the web (only in some configurations):
- `query` — string, **required**.
- `numResults` — number, optional (default 8).
- `livecrawl` — string, optional. `fallback` (default) or `preferred`.
- `type` — string, optional. `auto` (default), `fast`, or `deep`.
- `contextMaxCharacters` — number, optional (default 10000).

**todowrite** — maintain an in-session task list:
- `todos` — array, **required**. Each item:
    - `content` — string, **required**. Brief task description.
    - `status` — string, **required**. One of `pending`, `in_progress`, `completed`, `cancelled`.
    - `priority` — string, **required**. One of `high`, `medium`, `low`.

```json
{ "todos": [ { "content": "Run the new test suite", "status": "in_progress", "priority": "high" } ] }
```

**lsp** — code-intelligence queries (experimental; off unless enabled):
- `operation` — string, **required**. One of `goToDefinition`, `findReferences`, `hover`, `documentSymbol`, `workspaceSymbol`, `goToImplementation`, `prepareCallHierarchy`, `incomingCalls`, `outgoingCalls`.
- `filePath` — string, **required**. Path to the file.
- `line` — integer, **required**. 1-based line number.
- `character` — integer, **required**. 1-based character offset.
- `query` — string, optional. Only for `workspaceSymbol` (empty string requests all symbols).