\ TODO add words for asserting correctness
1 2 +
.s  \ exp: [3]

: a 5 ;
: b a ;
b
.s  \ exp: [3 5]

create e 7 ,
e @ .s  \ exp: [3 5 7]

5 e +!
e @ .s  \ exp: [3 5 7 12]
