// Global constants and variables
const PI: integer = 314;
let greeting: string = "Hello, Compiscript!";
let flag: boolean;

PI = 90;

let a = 10;        // INT_TYPE
let b = "hola";    // STRING_TYPE
let c = true;      // BOOL_TYPE
let d = null;      // NULL_TYPE

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