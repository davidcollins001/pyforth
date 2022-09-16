\ TODO add words for asserting correctness

1 2 +
.s  \ exp: [3]

: a 5 ;
: b a ;
b
.s  \ exp: [3 5]
drop drop

create e 7 ,
e @ .s  \ exp: [7]

5 e +!
e @ .s  \ exp: [7 12]
drop drop

' 1+
.s  \ exp: [87]

: c ' 1+ ;
c
.s  \ exp: [87 87]
