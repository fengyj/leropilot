# Leropilot Shell Integration for Bash

__leropilot_precmd() {
    local RETVAL="$?"
    # Emit Command Finished (D) with exit code
    # We only emit this if we are not in the very first prompt (which has no previous command)
    if [ -n "$__leropilot_initialized" ]; then
        printf "\033]633;D;%s\007" "$RETVAL"
    fi
    __leropilot_initialized=1

    # Emit Cwd (P)
    printf "\033]633;P;Cwd=%s\007" "$PWD"

    # Emit Prompt Start (A)
    printf "\033]633;A\007"
}

# Append to PROMPT_COMMAND
if [[ "$PROMPT_COMMAND" == *__leropilot_precmd* ]]; then
    :
else
    # Ensure PROMPT_COMMAND is a string
    PROMPT_COMMAND="${PROMPT_COMMAND:-}"
    # Prepend or append? Prepend ensures it runs before other things that might mess up output?
    # Actually, we want it to run just before the prompt.
    PROMPT_COMMAND="__leropilot_precmd; $PROMPT_COMMAND"
fi

# Append Input Start (B) to PS1
if [[ "$PS1" != *]633;B* ]]; then
    PS1="$PS1\[\033]633;B\007\]"
fi
