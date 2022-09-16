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
drop drop

\ jump back 3 + 2 added in `branch` to skip offset
: a dup swap 1- ;
: b a dup 0= 0branch -6 ;
4 b
.s  \ exp: [4, 3, 2, 1, 0]
drop drop drop drop drop
