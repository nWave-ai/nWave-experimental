/* Trust boundary: actual node:test callbacks, not exception prose or exit codes. */
export default async function* observation(events) {
  let observed = 0, assertions_failed = 0, setup_failed = 0;
  for await (const event of events) {
    // Require native declaration provenance, not successful container execution.
    if (
      event.type === "test:pass"
      && event.data.details?.type === "test"
      && typeof event.data.entryFile === "string"
      && !event.data.skip
      && !event.data.todo
    ) observed++;
    if (event.type === "test:fail") {
      const error = event.data.details?.error;
      if (error?.failureType === "testCodeFailure" && error?.cause?.code === "ERR_ASSERTION") {
        observed++;
        assertions_failed++;
      } else if (error?.failureType !== "subtestsFailed") {
        setup_failed++;
      }
    }
    if (event.type === "test:stdout" || event.type === "test:stderr") yield event.data.message;
  }
  yield "DES-ORACLE-OBSERVATION: " + JSON.stringify({version: 1, observed, assertions_failed, setup_failed}) + "\n";
}
