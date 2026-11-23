# Step 5: present and let the user choose

1. **By default, after every scan, give the user the dashboard.** Build it as described in
   [dashboard.md](../dashboard.md): fill the data block of the HTML template and print the full link. Show the
   Markdown table instead only if there is no template (a plugin install has none), the user declines the page, or
   you cannot create the file. Ask before opening the page in the browser (unless the user has just asked you to
   show it).
2. Apply [the eligibility table](04-classify.md) to both views. Show Red items as locked and Grey items
   with what is missing. Bind each group and link the complete manifest before showing its sample.
3. **Select nothing for the user.** Every item starts as Keep. Do not offer "all green". State what the user can
   choose and let them choose.
4. End with a single clear question: which items to clear, which to check first, or "none yet".
5. Accept changes. The user may ask for more detail on any item. Answer from the evidence you collected; if you
   need more, go back to step 3 for that item rather than guessing.

## Rules

- Show the cost next to every Yellow item (what is lost, or what must be rebuilt).
- Do not rank items by size alone. Mention rebuild cost and risk next to size.
- Show the selected logical size, estimated immediate gain and logical bytes pending in the bin for the
  named volume. Only show a projected shortfall if the immediate gain is known.
- Processes (memory) are never Green and are never part of a group choice.
- When the user included Codex diagnosis, show its aggregate summary in chat beside the HTML link or
  Markdown table. Exclude diagnostic counts and sizes from Clear, manifests and free-space projections.
- Nothing is deleted in this step.
