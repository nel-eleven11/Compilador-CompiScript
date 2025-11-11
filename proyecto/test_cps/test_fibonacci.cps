// Test Fibonacci - Multiple recursive calls
// Tests: double recursion, multiple stack frames

class Math {
    function fib(n: integer): integer {
        if (n <= 1) {
            return n;
        } else {
            return this.fib(n - 1) + this.fib(n - 2);
        }
    }
}

let math: Math = new Math();
let result: integer = math.fib(6);  // Should be 8
