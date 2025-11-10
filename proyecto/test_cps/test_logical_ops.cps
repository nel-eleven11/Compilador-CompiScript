// Test de operadores logicos
let a: boolean = true;
let b: boolean = false;

// Test AND
let and_result: boolean = a && b;  // Deberia ser false (1 && 0 = 0)

// Test OR
let or_result: boolean = a || b;   // Deberia ser true (1 || 0 = 1)

// Test NOT
let not_a: boolean = !a;           // Deberia ser false (! 1 = 0)
let not_b: boolean = !b;           // Deberia ser true (! 0 = 1)

// Test combinado
let combined: boolean = (a && !b) || (b && !a);  // (1 && 1) || (0 && 0) = 1 || 0 = 1
