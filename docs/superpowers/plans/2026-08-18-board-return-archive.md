# Board Return Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve interview-useful project code, evidence, and explanation materials in `zhuangxinyan-jennie/jichuang0713` before removing student code from the borrowed Ascend 310B board.

**Architecture:** Treat the board as the source of truth for final deployed runtime files, and treat the GitHub repository as the durable handoff. Only code, configuration templates, inventory manifests, and documentation should be committed; secrets, certificates, logs, generated caches, and large model/data artifacts should be excluded or summarized.

**Tech Stack:** Windows PowerShell, Git, Git LFS, Python Paramiko, Ascend 310B Linux board, project Python runtime, Unity frontend, React/Vite frontend.

## Global Constraints

- Do not delete board files until repository backup and push are verified.
- Do not commit board passwords, private keys, certificates, `.env` files, or API keys.
- Do not commit large generated archives, logs, caches, model checkpoints, or downloaded datasets unless already intentionally tracked by Git LFS.
- Preserve existing uncommitted user changes; do not revert unrelated edits.
- Before destructive cleanup, produce a final board file inventory and ask for explicit deletion-scope confirmation.

---

### Task 1: Repository and Board Inventory

**Files:**
- Create: `docs/BOARD_RETURN_INVENTORY.md`
- Create: `docs/INTERVIEW_PREP_ASCEND310B.md`
- Read: `/home/HwHiAiUser/pre_on_board`
- Read: `/home/HwHiAiUser/bear_agent_cloud`
- Read: `/home/HwHiAiUser/jichuang`
- Read: `/home/HwHiAiUser/HGBO`

**Interfaces:**
- Consumes: SSH access to `192.168.137.100` as `root`.
- Produces: A human-readable inventory that identifies durable source directories, runtime entrypoints, large excluded assets, and cleanup candidates.

- [ ] **Step 1: Confirm board login**

Run: Paramiko command `hostname; id; uname -a; df -hT`.
Expected: Hostname `davinci-mini`, uid `0(root)`, filesystem report.

- [ ] **Step 2: Inventory source directories**

Run: `find` over `/home/HwHiAiUser/pre_on_board/board_deploy`, `/home/HwHiAiUser/bear_agent_cloud`, `/home/HwHiAiUser/jichuang`, and `/home/HwHiAiUser/HGBO/scripts`.
Expected: File list with permissions, owners, sizes, modification times.

- [ ] **Step 3: Identify exclusions**

Run: `find /home/HwHiAiUser -xdev -type f -printf '%s %p\n' | sort -nr | head`.
Expected: Large models, archives, caches, and logs are listed as excluded or summarized.

- [ ] **Step 4: Write inventory docs**

Add concise project inventory and interview-prep notes. Mention core contributions from resume: streaming ASR NPU deployment, CTC state management, Ascend C auto-tuning, board-runtime integration, and Unity/agent interaction chain.

### Task 2: Preserve Board Source Files

**Files:**
- Modify: `pre_on_board_local_start_bundle/board_deploy/**`
- Modify: `pre_on_board_local_start_bundle/jichuang/**`
- Modify: `bear_agent/tools/**` if deployment tooling needs documentation updates
- Create: `archive/live_board_snapshot_20260818/README.md`

**Interfaces:**
- Consumes: Board inventory from Task 1.
- Produces: Repository paths that point to the final board source of truth without private credentials.

- [ ] **Step 1: Compare live board files with repo copy**

Hash selected live files and local files: board runtime, app gateway, crowd flow, ASR receiver, speaker player, and launch scripts.
Expected: Changed files are known before copying.

- [ ] **Step 2: Copy only source/config files**

Copy `.py`, `.sh`, `.md`, `.json`, `.yaml`, `.cfg`, `.service`, and small static assets. Exclude `__pycache__`, `.log`, `.pid`, `.tar.gz`, `.onnx`, `.om`, `.npz`, `.pt`, `.wav`, certificates, and secret env files.

- [ ] **Step 3: Re-run secret scan**

Run a staged-content scan for passwords, private keys, API keys, and provider key prefixes on newly staged paths.
Expected: No committed secret remains, except sanitized documentation examples.

### Task 3: Publish and Verify GitHub Backup

**Files:**
- Commit selected changed files.
- Push branch `main` or a `codex/board-return-archive` branch, depending on working tree safety.

**Interfaces:**
- Consumes: Clean staged set from Tasks 1-2.
- Produces: Remote GitHub commit containing board source inventory and interview notes.

- [ ] **Step 1: Inspect staged diff**

Run: `git diff --cached --stat` and `git diff --cached --check`.
Expected: No unwanted deletions, secrets, or whitespace errors.

- [ ] **Step 2: Commit**

Run: `git commit -m "docs: archive board return materials"`.
Expected: Commit succeeds.

- [ ] **Step 3: Push**

Run: `git push origin HEAD`.
Expected: GitHub remote receives the commit.

### Task 4: Board Cleanup

**Files:**
- Remove from board only after confirmation:
  `/home/HwHiAiUser/pre_on_board`,
  `/home/HwHiAiUser/pre_on_board_tmp`,
  `/home/HwHiAiUser/bear_agent_cloud`,
  `/home/HwHiAiUser/jichuang`,
  `/home/HwHiAiUser/HGBO`,
  related root-owned archives and runtime logs.

**Interfaces:**
- Consumes: Verified GitHub commit hash.
- Produces: Board with student project code removed.

- [ ] **Step 1: Ask for deletion scope confirmation**

Expected: User explicitly approves exact board paths to delete.

- [ ] **Step 2: Stop project services and processes**

Run safe process listing first, then stop only project commands.
Expected: No project runtime is using files.

- [ ] **Step 3: Move or delete approved paths**

Prefer a temporary quarantine directory if time allows; otherwise delete approved project paths.
Expected: `find` confirms removed paths are gone.

- [ ] **Step 4: Final verification**

Run `df -hT`, `ls -la /home/HwHiAiUser`, and `find` checks for remaining project directories.
Expected: Board no longer contains selected student project files.
