# Repository Guidelines

## Project Structure & Module Organization

This repository is a compact static frontend project. The primary application artifact is `frontend/MGS Debug Console.html`, a self-contained bundled HTML page for the MGS Debug Console. There are no separate source, test, or asset directories at this time; bundled JavaScript, styles, images, and template data live inside the HTML file. `LICENSE` contains the project license.

If the project grows, keep source files under `frontend/src/`, static assets under `frontend/assets/`, and tests near the code they cover or in `frontend/tests/`.

## Build, Test, and Development Commands

No package manager, build system, or automated test command is currently defined. Useful local commands:

- `open "frontend/MGS Debug Console.html"`: view the console in the default browser on macOS.
- `python3 -m http.server 8000`: serve the repository locally if browser behavior differs under `file://`; then open `http://localhost:8000/frontend/MGS%20Debug%20Console.html`.
- `git status --short`: check pending changes before editing.

Add documented scripts before introducing generated assets or multi-step builds.

## Coding Style & Naming Conventions

Preserve the existing single-file HTML structure unless you are intentionally unbundling the app. Use two-space indentation for HTML, CSS, and JavaScript blocks, matching the current file. Prefer descriptive function and state names such as `toggleSelect`, `connectAll`, and `visibleLines`.

Keep user-facing labels consistent with the existing interface language. The current UI includes Korean labels and robot/debug-console terminology, so avoid changing copy casually.

## Testing Guidelines

There is no automated test suite yet. For changes to `frontend/MGS Debug Console.html`, manually verify the page loads, the robot list renders, terminal panes update, filters work, and command input responds. Test both direct file opening and local HTTP serving when editing bundle loading, blob URL handling, or browser APIs.

If tests are added, document the framework and name files with clear patterns such as `*.test.js` or `*.spec.js`.

## Commit & Pull Request Guidelines

Git history currently only shows `Initial commit`, so no project-specific convention is established. Use concise imperative commit messages, for example `Update debug console terminal filters`.

Pull requests should describe the visible behavior changed, list manual verification steps, and include screenshots or short screen recordings for UI changes. Link related issues when available and call out any browser compatibility risks.

## Agent-Specific Instructions

Before editing, check whether a requested file already exists if the task mentions preservation. Do not overwrite bundled HTML output without understanding whether it is the source of truth or generated from another tool.
