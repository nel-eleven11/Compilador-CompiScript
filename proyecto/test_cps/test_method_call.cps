// Test method call (which does generate proper call quadruples)

class Calculator {
    function add(a: integer, b: integer): integer {
        return a + b;
    }
}

let calc: Calculator = new Calculator();
let result: integer = calc.add(5, 10);

print(result);
