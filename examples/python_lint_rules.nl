Function {fn} may swallow errors if
    Function {fn} catches a broad exception and
    Function {fn} has an exception path that does not re-raise.

Function {fn} mixes persistence and notification if
    Function {fn} writes persistent state and
    Function {fn} sends a notification.

Function {fn} needs decomposition if
    Function {fn} is long and
    Function {fn} mixes persistence and notification.

Function {fn} needs review if
    Function {fn} may swallow errors or
    Function {fn} needs decomposition.
