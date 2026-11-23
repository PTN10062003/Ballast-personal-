# Step 4: classify

Turn evidence into a tier. Apply the rules **in order**; the first one that matches wins.

1. **Protected name (E7) matches → Red.** Done. Never selectable, and nothing the user says changes it.
2. **Unsaved work (E5) or cloud/shared (E6) → Red.** No exception. If the user says it is disposable, tell them how
   to remove it by hand.
3. **Is it a program (E3)? → not a cache.** Do not offer folder deletion. If the user wants the program removed,
   that is the vendor's own uninstaller, with their approval (H14). The program's data folders stay Red or Grey
   unless a catalog row says otherwise.
4. **Any check is unknown, errored, or incomplete → Grey.** This includes a process whose path you could not read.
5. **In use now (E2) → Grey.** Never selectable while in use, whatever the catalog row says. Explain what is using it.
6. **Anything depends on it (E4) → Yellow at best**, and name what would break. (An item that is also in use is Grey
   by rule 5 first.)
7. **A catalog row matches and nothing above applies →** the row's tier. Age does not change the tier: show it, with
   a "Heads up" note when it is recent (see [cleanup.md](../cleanup.md)), and let the user decide.
8. **No catalog row → Grey.**

**Attribution Low → Grey**, unless rules 1 to 3 already made it Red. A Low attribution never turns a Red item Grey.

## Rules of thumb

- Rebuildable and cheap (cache, build output, download) → Green or Yellow.
- Loses information (chat history, session data) → Yellow, with the loss named.
- Anything an app needs to sign in or remember you → Red.
- Items inside scratch or temporary folders may hold the only copy of something an agent made. Do not treat them as
  disposable without asking (H0).
- When in doubt, go one tier more cautious and ask.

## Output of this step

A file or folder's highest eligible tier is given by [policy.json](../policy.json). Use this same table
at classification, for both dashboards, and again just before acting. Check the actual catalog match,
status, scope, row-specific conditions and the [path guard](06-approve-and-run.md#path-guard) first.
An absent match, an unresolved identity, an error, or an unconfirmed row condition withholds Clear.
Currently all file rows listed in the table describe Windows. The Linux and macOS starter rows are Grey.
Processes and the volume bin have separate procedures and cannot be selected for a generic file deletion.

1. Start with the catalog tier, capped by the supplied tier. Apply the most restrictive result in the
   order Green, Yellow, Grey, Red. Retain any Red finding even if another check failed.
2. Look up the exact row in `fileRows` and the attribution in `makers`. Each value is a tier cap.
   A missing entry caps the item at Grey. Name the extra uncertainty of a row marked `review`.
3. Require one result per check E1–E8 with a nonempty observation. For each check, look up its state
   in `checks`. Missing, unknown, duplicate, unreadable and unrecognized results cap the tier at Grey.
   An E1 note reports recency. An E4 or E8 note reports a **known** dependency or recovery cost and
   caps the item at Yellow. A positive E2 finding is `block`. An installed program, unsaved work,
   cloud/shared data or protected path is `block` on E3, E5, E6 or E7 respectively and makes it Red.
4. No file/folder check may be waived as `na`. For example, a completed check showing zero dependants
   is E4 `ok` with the observation. Other item types may display `na` as information only.
5. Record the measured logical size, volume, scan identity, tier, evidence, attribution, recovery cost
   and exact removal method. Temp rows require Permanent. Offer Clear only for an eligible Green or
   Yellow disk item. If evidence changes, reclassify and apply the approval rules again.
