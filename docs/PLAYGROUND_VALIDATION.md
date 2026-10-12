# Playground validation — 2026-10-12

The standalone HTML/CSS/JavaScript playground uses the existing worker interface;
no inference code or published container contents changed.

- `node --check playground.js` and `node --check playground-core.js` passed.
- Twelve Node tests passed: endpoint normalization/credential destination,
  space-tolerant mentions, missing references, stable identities after removal,
  worker payload shape, size/seed/reference/payload bounds, async completion,
  status recovery without resubmission, refresh without automatic requests,
  terminal job and worker errors, uncertain submission without retry,
  cancellation on the saved endpoint and forgetting a saved key.
- Browser verification used `http://127.0.0.1:8765/playground.html`: endpoint,
  fake API key, prompt and portrait dimensions survived a reload; fake credentials
  were removed afterwards. Two local test images uploaded successfully.
- `@picture1 is the character. Follow @picture 2's pose.` translated to
  `Picture 1 is the character. Follow Picture 2's pose.`. Removing picture 1 kept
  picture 2's label stable and blocked generation with the missing-reference
  message before any API call.
- Exported JSON had only the worker's five input fields. The opaque reference
  was JPEG; the transparent reference was PNG with alpha 128 preserved.
- Mobile viewport 390×844 had equal document content/client widths (375 px),
  with settings/composer/result stacked. Desktop layout was visually inspected.
- Browser console inspection returned no warnings or errors.

Job lifecycle tests execute the actual UI controller with a small mocked DOM
and mocked RunPod responses; they are not live API or GPU-generation evidence.
No real API key was entered and no paid generation was submitted. Live image
quality, reference adherence and GPU memory still need the configured endpoint.

Browser screenshots and test reference images are in ignored `.validation/`.
