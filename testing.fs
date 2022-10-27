\ Simple support for unit tests

0 variable tests-fail
0 variable tests-pass
: fail-tests 1 tests-fail +! ;
: pass-tests 1 tests-pass +! ;

: test-summary ( -- )
  ." ** "
  tests-fail @ ?DUP if ." TESTS FAILED! " else
  depth 0<> if ." TESTS OK but stack not empty: " .s else
  ." TESTS RAN OK " then then
  ." -- " tests-fail @ . ." failed " tests-pass @ . ." passed"
  space ." **"
  ;

: =assert ( n1 n2 -- ) \ assert that the two TOS values must be equal
  2dup <> if ." FAIL: got " . ." expected " . CR fail-tests
  else 2drop pass-tests then ;

: ?assert ( f -- ) \ assert that the flag on TOS is true
  0= if ." FAIL!" fail-tests
  else ." OK!" pass-tests then ;
