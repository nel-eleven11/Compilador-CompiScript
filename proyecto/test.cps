// Operaciones logicas validas
let a: boolean = true && false;
let b: boolean = true || false;
let c: boolean = !true;

// Operaciones logicas invalidas
let d: boolean = 1 && true;      // Error
let e: boolean = "hola" || false; // Error
let f: boolean = !5;             // Error

// Comparaciones validas
let g: boolean = 5 == 5;
let h: boolean = "a" == "a";
let i: boolean = null == null;
let j: boolean = "texto" == null;

// Comparaciones invalidas
let k: boolean = 5 == "5";       // Error
let l: boolean = true == 1;      // Error
let m: boolean = null == 10;     // Error

// Operaciones relacionales validas
let n: boolean = 5 < 10;
let o: boolean = 10 >= 5;

// Operaciones relacionales invalidas
let p: boolean = 5 < "10";       // Error
let q: boolean = true > false;   // Error

let pa: boolean = (1 == 1) != (2 > 3);
let pb: boolean = "hola" == null;
let ps: boolean = true && (5 == 5);