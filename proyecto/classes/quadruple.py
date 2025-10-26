# quadruple.py clase que representa un quadruplo
# para la generacion de codigo intermedio

class Quadruple:
    def __init__(self, op, arg1, arg2, result, comment=None):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.result = result
        self.comment = comment  
    
    def __str__(self):
        base = f"({self.op}, {self.arg1}, {self.arg2}, {self.result})"
        if self.comment:
            return f"{base}  # {self.comment}"
        return base