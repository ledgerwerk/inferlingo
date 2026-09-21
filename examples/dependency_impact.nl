"web" depends on "api".
"api" depends on "auth".
"auth" depends on "database".
"database" is unavailable.

{service} is affected if
    {service} depends on {dependency} and
    {dependency} is unavailable.

{service} is affected if
    {service} depends on {dependency} and
    {dependency} is affected.
