/**
 * OpenCode's counterpart to the Claude Code `SessionStart` hook: refreshes the GitHub issue cache
 * (AGENTS.md, "Tracking open work") once per session and puts `.claude/cache/issues/index.md` into that
 * session's system prompt.
 *
 * Both halves run in the `context` session hook, which fires before every model request:
 *   - A session's first request runs `.claude/hooks/session-start.sh`, which owns the `gh`-or-REST-API
 *     choice, and waits for it up to `REFRESH_TIMEOUT_MS`. Its printed index is discarded. A refresh that
 *     times out or fails leaves the previous run's cache in place. `CLAUDE_CODE_REMOTE` is unset here, so
 *     the hook stops after the cache refresh and never runs its cloud setup block.
 *   - The index is read once per session and pushed onto `event.system` on every request. The text is held
 *     per session so a later session's refresh never changes an earlier session's prompt mid-conversation.
 *
 * Sessions created within `REFRESH_REUSE_MS` of a refresh share it, so a burst of subagent sessions costs
 * one fetch against the REST API's unauthenticated rate limit.
 *
 * OpenCode reads `id` and `setup` off the default export. The definition object is written out rather than
 * built with `Plugin.define` because that needs `@opencode/plugin`, and this repo has no OpenCode Node
 * dependency (AGENTS.md, "Conventions"). The file runs under OpenCode's own loader, outside any Node
 * project, so the context types are local.
 */

import { execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

const INDEX_PATH = '.claude/cache/issues/index.md';
const REFRESH_TIMEOUT_MS = 20_000;
const REFRESH_REUSE_MS = 60_000;

type ContextEvent = {
  sessionID: string;
  system: { type: 'text'; text: string }[];
};

type PluginContext = {
  location: { directory: string };
  session: {
    hook(name: 'context', handler: (event: ContextEvent) => Promise<void>): Promise<unknown>;
  };
};

export default {
  id: 'intrapaint.issue-cache',
  async setup({ location, session }: PluginContext) {
    const root = location.directory;
    let refresh: { started: number; done: Promise<void> } | undefined;
    const indexBySession = new Map<string, Promise<string | undefined>>();

    const runRefresh = () =>
      new Promise<void>((resolve) => {
        execFile(
          'bash',
          ['.claude/hooks/session-start.sh'],
          { cwd: root, timeout: REFRESH_TIMEOUT_MS },
          () => resolve(),
        );
      });

    const loadIndex = async () => {
      if (!refresh || Date.now() - refresh.started > REFRESH_REUSE_MS) {
        refresh = { started: Date.now(), done: runRefresh() };
      }
      await refresh.done;
      return readFile(path.join(root, INDEX_PATH), 'utf8').catch(() => undefined);
    };

    await session.hook('context', async (event) => {
      let index = indexBySession.get(event.sessionID);
      if (!index) {
        index = loadIndex();
        indexBySession.set(event.sessionID, index);
      }
      const text = await index;
      if (text) event.system.push({ type: 'text', text: `Instructions from: ${INDEX_PATH}\n${text}` });
    });
  },
};
