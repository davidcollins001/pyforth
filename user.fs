

: .s        ( -- )
    '[' EMIT
    DEPTH 1- 0 DO
        S0 @ I + @ .    ( print the stack element )
    LOOP
    \ SPACE ':' EMIT SPACE
    ." TOS: "
    S0 @ DEPTH 1- + @ 0 .R
    ']' EMIT '\n' EMIT
;


1 2 3 4 .s
