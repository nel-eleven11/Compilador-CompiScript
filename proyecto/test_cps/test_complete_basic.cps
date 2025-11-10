// test_complete_basic.cps
// Test completo de TODAS las operaciones basicas implementadas

let a: integer = 15;
let b: integer = 4;
let result: integer = 0;

// Test aritmetica completa
let sum: integer = a + b;           // 19
let diff: integer = a - b;          // 11
let prod: integer = a * b;          // 60
let quot: integer = a / b;          // 3
let mod: integer = a % b;           // 3

// Test negacion unaria
let neg: integer = -b;              // -4

// Test comparaciones
let is_greater: boolean = a > b;    // true (1)
let is_equal: boolean = a == b;     // false (0)
let is_less_eq: boolean = a <= b;   // false (0)

// Test control de flujo
if (a > b) {
    result = a;
} else {
    result = b;
}
// result deberia ser 15

// Test combinado: expresion compleja
let complex: integer = (a + b) * 2 - mod;  // (15+4)*2 - 3 = 38 - 3 = 35
