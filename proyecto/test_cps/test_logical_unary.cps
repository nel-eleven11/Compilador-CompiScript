// test_logical_unary.cps
// Test logical operations, unary operations, and modulo

let a: integer = 10;
let b: integer = 3;
let c: integer = 0;

// Test unary negation
let neg_a: integer = -a;  // Should be -10

// Test modulo
let mod_result: integer = a % b;  // 10 % 3 = 1

// Test logical NOT
let x: boolean = true;
let not_x: boolean = !x;  // Should be false

// Test arithmetic and negation
c = a + neg_a;  // Should be 0 (10 + (-10))

// Results:
// neg_a = -10
// mod_result = 1
// not_x = false (0)
// c = 0
