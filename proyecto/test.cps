// Suma de enteros
let a: integer = 1 + 2;
let b: integer = 3 * 4 - 5;
let c: integer = (1 + 2) * 3;

// Variables con enteros
let x: integer = 10;
let y: integer = 20;
let z: integer = x + y;

// Encadenamiento
let result: integer = 1 + 2 + 3 + 4;
let result2 = 1 + 2 + 3 + 4 + "a";


// Mezcla de integer y string
let a1: integer = 1 + "a";           // Error
let b1: integer = "hola" * 5;        // Error
let c1: integer = 10 - true;         // Error

// Operacion con null
let d1: integer = 10 + null;         // Error

// Encadenamiento con error en medio
let e1: integer = 1 + "b" + 3;       // Error propagado, no repetir multiples veces

// Variable sin tipo declarado, pero inicializacion invalida
let f1 = 1 + "hola";          

