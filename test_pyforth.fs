include testing.fs


: test:+ + =assert ;
3 1 2 test:+
2 0 2 test:+
0 -1 1 test:+

: a 5 ;
: b a ;
: test:word-in-word
  5 b =assert ;
\ test:word-in-word

 7 variable e
17 constant f
: test:create
  7 e @ =assert
  5 e +!
  12 e @ =assert ;
test:create
17 f =assert

: test:tick
  ['] 1+ ;
' 1+ test:tick =assert
3 2 ' 1+ execute =assert
3 2 test:tick execute =assert

\ jump back 3 + 2 added in `branch` to skip offset
: c dup swap 1- ;
: d c dup 0= 0branch -6 ;
4 d
0 swap =assert
1 swap =assert
2 swap =assert
3 swap =assert
4 swap =assert

4 3 2 1 0
: test:loop 5 0 do i =assert loop ;
test:loop

:noname 3 ;
: test:noname execute 3 =assert ;
test:noname

test-summary
