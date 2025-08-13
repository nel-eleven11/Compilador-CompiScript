// Global constants and variables
const PI: integer = 314;
let greeting: string = "Hello, Compiscript!";
let flag: boolean;

PI = 90; // error, no se peude reasignar

const PI: integer = 3;
const NAME = "Alice";  // Tipo inferido
const FLAG: boolean = true;

const UNINITIALIZED;  // Error: falta inicializacion
const BAD: integer = "text";  // Error: tipo incorrecto
const NULL_CONST = null;  // Error: requiere tipo explicito
let a1: integer = 10;
let b1: string = "hola";
let c1: boolean = true;
let d1 = null;

function greet(name: string) {
    print("Hello " + name);
    return "hi";
}

function greet(name: string): string {
    print("Hello " + name);
    return "hi";
}

function greet_num(name: string): integer {
    print("Hello " + name);
    return "hi";
}

let a2: integer = 10;
let b2: string = "hola";
let c2: boolean = true;
let d2 = null;

let z = null;      // Tipo null inicialmente
z = "hola";        // a

// Array de enteros explicito
let nums: integer[] = [1, 2, 3];

// Array de strings inferido
let names = ["a", "b", "c"];

// Array multidimensional
let matrix: integer[][] = [[1, 2], [3, 4]];
