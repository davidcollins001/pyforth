\ TODO add words for asserting correctness

1 2 +
.ds  \ exp: [3]

: a 5 ;
: b a ;
b
.ds  \ exp: [3 5]
drop drop

create e 7 ,
e @ .ds  \ exp: [7]

5 e +!
e @ .ds  \ exp: [7 12]
drop drop

' 1+
.ds  \ exp: [87]

: c ' 1+ ;
c
.ds  \ exp: [87 87]
drop drop

\ jump back 3 + 2 added in `branch` to skip offset
: a dup swap 1- ;
: b a dup 0= 0branch -6 ;
4 b
.ds  \ exp: [4, 3, 2, 1, 0]
drop drop drop drop drop

.ds \ exp: []
