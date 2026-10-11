// Exercise the generated extension's public factory without model/network calls.
// The installed shim path is runtime-selected by the isolated test destination.
const { default: extension, translateToolCalls } = await import(Bun.argv[2]);
let toolCall: Function | undefined;
extension({
  on(event: string, callback: Function) {
    if (event === "tool_call") toolCall = callback;
  },
});
if (!toolCall) throw new Error("The extension did not register tool_call");
const ctx = {
  cwd: process.env.HOME!,
  sessionManager: { getSessionId: () => "omp-installer-probe" },
  agent: { kind: "main", name: "main" },
};
const blocked = await toolCall({ toolName: "bash", input: { command: "git stash push" } }, ctx);
const allowed = await toolCall({ toolName: "bash", input: { command: "pwd" } }, ctx);
const batch = translateToolCalls("task", {
  context: "Shared instructions",
  tasks: [{ task: "First", agent: "nw-software-crafter" }, { task: "Second", agent: "nw-product-owner" }],
});
const write = translateToolCalls("write", { path: "file.py", content: "value" });
const uri = translateToolCalls("write", { path: "xd://device", content: "{}" });
const hashline = translateToolCalls("edit", { input: "[file.py#1234]\nPUT 1.=1:\n+value" });
console.log(JSON.stringify({ blocked, allowed: allowed ?? null, batch, write, uri, hashline }));
const hashlineMoves = translateToolCalls("edit", {
  input: "[old.py#1234]\nMV \"new file.py\"\n[execution-log.json#ABCD]\nREM",
});
const applyPatch = translateToolCalls("edit", {
  input: "*** Begin Patch\n*** Update File: first.py\n*** Move to: second.py\n*** End Patch",
});
console.log(JSON.stringify({ hashlineMoves, applyPatch }));
