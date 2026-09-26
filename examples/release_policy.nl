# Release readiness is derived from exact facts supplied by application adapters.
# @rule release-ready
# @description A service can ship only when CI, change approval, security, and freeze checks pass.
{service} is release-ready if
    {service} has passing tests and
    {service} has an approved change and
    {service} has acceptable vulnerability status and
    not {service} is frozen.

# @rule blocker-tests
# @description Report failed CI as an actionable release blocker.
{service} has blocker "tests failing" if
    {service} has failing tests.

# @rule blocker-approval
# @description Require approved change evidence when change management says approval is needed.
{service} has blocker "change not approved" if
    {service} needs change approval and
    not {service} has an approved change.

# @rule blocker-vulnerabilities
# @description Escalate critical scanner findings before release.
{service} has blocker "critical vulnerabilities" if
    {service} has critical vulnerabilities.

# @rule blocker-freeze
# @description Keep services out of an active release freeze.
{service} has blocker "release freeze" if
    {service} is frozen.
