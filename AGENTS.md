# Mondeora listing changes

For every new product, listing preparation, revision, scheduled audit and orchestrator task, load the user skill `listing-repeatable-quality` and follow its evidence-first procedure. It is the common standard, not a per-product recipe.

- Inspect `src.jobs` entry points. Use `listing_standards` for the bounded GET-only recurring review queue; preparation is `listing_prepare`, release consumes saved plans only.
- Unknown required facts block; unknown optional facts become review items. Never fill a field merely to reach an aspect count. Competitor data are suggestions, not proof of our SKU's characteristics.
- Do not substitute shipping-package dimensions for product dimensions, a brand placeholder for manufacturer identity, or same-colour pack/model variants for one SKU.
- Require real buyer readback even in supervised trials. Preserve ambiguous writes for reconciliation; do not mark unperformed checks verified.
- Never delete the ready database or another process's lock as a normal refresh. Preserve publication history, daily limits and reconciliation state.
- Develop in an isolated current-source snapshot. Run failing regression tests first, the full suite after edits, then deploy only reviewed files with unchanged-source preconditions and backups. Do not copy credentials or live databases into tests.
- Use structured safe error codes/types, never raw provider bodies or buyer data. A partial scan remains partial; a scheduled cron has not necessarily run.
- Skill text is not runtime code. Prove the function, caller, scheduled entry point, saved result and exact target readback before reporting automation complete.
