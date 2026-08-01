<EXTREMELY-IMPORTANT>
**Before your next reply, answer this: is what you are reading right now the FULL
orchestrator-affordance catalog, or only a truncated preview of it — and if you cannot
be sure, have you actually opened the full file with the Read tool yet, or only skimmed
a preview that looked close enough to what you already expected?** A preview that
"looks consistent with what you already know" is not a reason to answer yes without
checking — that is exactly the failure mode this paragraph exists to catch, and it has
already happened at least once: an instance saw only this 2KB preview after a restart,
noticed the message telling it to Read the full file, and did not do it before replying.

If you see a line like "Full output saved to: <path>" above/below this block: that path
IS this same catalog, re-rendered as a tool-result — Read <path> with the Read tool NOW.
If no such <path> is given, Glob `**/orchestrator-affordance/*.md` and read what it
returns: this is the orchestrator-affordance catalog injected by the DES runtime, and its
directory is at a DIFFERENT absolute path in a dev checkout, a Claude-Code install and a
host-neutral install — so a literal path here would misdirect two readers out of three,
whereas that Glob resolves in all of them. If the Glob returns nothing, the affordance is
not installed where this session can reach it, and THAT is the finding — report it rather
than proceeding as if you had read the file. This paragraph is deliberately first (sorts
before every other asset in this directory) so the question survives even a 2KB-preview
cut — but a question only works if you actually answer it before moving on, not after.
</EXTREMELY-IMPORTANT>
