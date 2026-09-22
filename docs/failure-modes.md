# Environmental failure modes

Failures worth testing for specifically, because they don't show up when
reading source or config; only when the lab is actually run.

## Log collector gives up on a file that didn't exist at startup

Most host-based log collectors retry opening a configured file a fixed
number of times at startup, then
stop watching it permanently if it's still missing. If a detection
mechanism writes to a log file that gets created *after* the collector
starts, the collector silently drops that file from its watch list. The
detector keeps writing, nothing reads it, and every service reports
healthy.

**Test for it:** after the full build, check the collector's own log for
an "ignoring" or "not available" message about each file you expect it to
tail. Confirm the *last* mention for each file is a successful open, not a
give-up. An early failure followed by a later success (after you fixed
the ordering) is fine; a give-up with no later success is not.

## Polling loses the race against a target that grows on its own

A file-size or hash-based poller assumes the target is quiet between
samples. If the target also grows under normal operation (a log file
being appended to by unrelated processes), an attacker can shrink it and
let it regrow past the previous sample before the next tick. The poller
sees no drop, or a drop that doesn't correspond to the real event.

Shortening the polling interval narrows this window but doesn't close it;
a fast enough action still fits between two samples. The only fix is
switching from polling to an event-driven mechanism (inotify or
equivalent) that fires on the change itself, not on a periodic snapshot.

**Test for it:** run the attack once with the detector on its documented
interval, then again as fast as the tooling allows. Both must be caught.
If the fast run isn't, polling is the design and it needs to move to
event-driven detection, not a shorter interval.

## Build order dependencies that aren't written down

A step early in the build guide can silently depend on a step written
later: a package installed in a later section, a file created by a step
the author assumed came first. These don't fail during authoring, because
the author's own build happened to be in the right order.

**Test for it:** a clean-room rebuild from a pristine image, executing the
build guide exactly as written, with nothing done out of band. Any command
that fails, or any manual fix applied outside the documented steps, is a
build-guide bug.

## A validator that passes on stale state

An end-to-end validator that only checks "does the expected artifact
exist" rather than "did *this run* produce it" will pass against leftover
state from a previous run, even if the current run's detection completely
failed. This hides real regressions during iteration.

**Test for it:** run the validator twice in a row against the same target
without resetting between runs. It should only pass the second time if the
second run's own attack actually triggered the expected detection:
timestamp or count checks against a captured baseline, not just presence
checks.

## The intended obstacle has a bypass

For a lab that gates a flag behind exploiting a vulnerability, check
whether the flag or an equivalent shortcut is reachable without going
through the intended path: a leftover credential, a world-readable copy,
a tool the attacker's own setup left behind that a solver could reuse
directly. If validation and staging aren't done in a fixed order, tooling
used to verify the lab can itself leave that shortcut behind on the
snapshot that ships.

**Test for it:** as the lowest-privilege account the lab provides, try to
reach the goal without performing the intended exploit. It should fail.
Then check every artifact the build or validation process leaves behind
and confirm none of them are that shortcut.

## Sample data drifts from what the running system actually produces

Sample logs, screenshots, and worked examples written by hand tend to
drift from real output: wrong field names, a format the code no longer
emits, or a description that was true of an earlier design revision. This
compounds with the point above: if a rule matches on the literal string
of a log line, changing the emitting code without checking the rule
against a real sample breaks detection with no compile-time or config-time
warning.

**Test for it:** regenerate sample data and documentation screenshots from
a real run of the finished system, not from what the design doc says the
output should look like.
