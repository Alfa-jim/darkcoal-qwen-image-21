# Personal Qwen 2.1 playground

The existing sibling workers have standalone HTML playgrounds. This one follows
that local-tool pattern with no framework, build step, remote scripts or proxy.
The user requested saved RunPod URL/key settings, preconfigured Turbo sampling,
and uploaded pictures addressable in the prompt as `@picture1` or `@picture 2`.

Use a restrained charcoal interface for the user's existing Darkcoal workspace:
one lime accent for the primary action and active reference labels, system text,
readable form labels, a settings sidebar and adjacent composer/result panels.
At smaller widths the result moves below the composer; on phones the sidebar
also stacks. All actions have keyboard focus styles and notices are live regions.

Connection settings and generation fields use a versioned localStorage key. The
API key is intentionally saved, as requested, masked in the UI and removable.
Only the official HTTPS RunPod API origin is accepted as a credential destination.
Uploads/results stay in memory. Exports contain input data without credentials.

Reference IDs survive removal, while the submitted array retains visible order.
Mentions compile to the engine's native positional `Picture N` wording. Missing
mentions prevent submission; the translated prompt is inspectable. Browser image
preparation applies orientation, shrinks to 1024 pixels and preserves alpha.

Sampling belongs to the existing worker: eight Euler steps, CFG 1 and its pinned
Turbo sigmas. The playground only sends prompt, ordered images, width, height and
seed. It submits once through `/run`, polls `/status/{id}`, and can request cancel.
Job IDs survive refresh; resuming only checks status. A submission failure is
never automatically retried because the upstream job may have been accepted.

Verification combines pure input/mention tests, the actual controller executing
against a mocked RunPod API, and browser checks for uploads, persistence,
translation, request export and responsive layout. Live GPU inference requires
the user's prepared volume and configured endpoint.
