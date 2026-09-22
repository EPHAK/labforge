# Validation checklist

Run before a lab is considered done. Every item requires actually running
something on a real guest; none of these are satisfied by reading code
or config.

## Build

- [ ] Build guide executed verbatim on a pristine image, start to finish,
      with no manual fix applied outside the documented steps.
- [ ] Every command in the build guide exits successfully; failures aren't
      swallowed or worked around silently.
- [ ] Package/dependency lists are complete; nothing installed by hand
      during testing that isn't also in the documented install step.
- [ ] Ordering dependencies are correct: nothing in an early step relies
      on something a later step installs or creates.

## Detection (for defend-style labs)

- [ ] The attack is run at least twice against a fresh build, confirming
      identical detection each time.
- [ ] The attack is run once with the detector on its normal interval and
      once as fast as tooling allows, if the detector polls. Both must be
      caught, or the design needs to be event-driven rather than polled.
- [ ] The collector or agent's own logs are checked after the build for
      any "file not found" or "ignoring" messages about files the
      detection depends on.
- [ ] The detection rule is tested against a real captured log line, not
      a line typed by hand from memory of the format.

## Validator (autopwn / automated check)

- [ ] Run twice in a row without resetting the target between runs. The
      second run only passes if its own attack triggered its own
      detection, not because of state left over from the first run.
- [ ] Run from the exact archive that will be submitted or shipped, not
      from a working copy that may have diverged.
- [ ] Failure paths are checked, not just the success path; deliberately
      break one precondition (stop the detection service, remove a
      dependency) and confirm the validator reports the correct cause.

## Shortcuts and unintended solutions

- [ ] As the lowest-privilege account provided, attempt to reach the goal
      without performing the intended exploit or investigation. It should
      fail.
- [ ] Every artifact left behind by the build or validation process is
      checked for permissions and content; nothing usable as a bypass is
      present in the shipped state.
- [ ] If build/validation tooling can itself trigger the vulnerable
      condition, confirm the order of operations before snapshotting
      doesn't leave that condition active in the final state.

## Documentation

- [ ] Every command shown in the walkthrough or build guide has been run
      for real and produces the output shown.
- [ ] Screenshots and sample logs are captured from a real run, not typed
      by hand.
- [ ] Values quoted in prose (timestamps, sizes, IDs) match the actual
      captured output, not a placeholder or an earlier run's values.
- [ ] No leftover references to an earlier design (old file names, old
      log formats, old messages) remain in prose or sample data after a
      redesign.

## Packaging

- [ ] The archive that will actually be submitted is extracted fresh and
      tested, not a working directory that happens to match it.
- [ ] Archive paths use forward slashes regardless of the platform used to
      build it.
- [ ] The archive layout matches the target platform's own reference
      example, not an assumed structure.
