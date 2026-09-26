"checkout-web" depends on "checkout-api".
"checkout-api" depends on "payments".
"payments" depends on "postgres-primary".
"postgres-primary" is unavailable.

# @rule directly-affected-by-outage
# @description A service is affected when one of its direct dependencies is unavailable.
{service} is affected if
    {service} depends on {dependency} and
    {dependency} is unavailable.

# @rule transitively-affected
# @description Propagate an outage through the service dependency graph.
{service} is affected if
    {service} depends on {dependency} and
    {dependency} is affected.
