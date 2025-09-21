# quadruple.py clase que representa un quadruplo
# para la generacion de codigo intermedio

class Quadruple:
    def __init__(self, op, arg1, arg2, result):
        self.op = op
        self.arg1 = arg1
        self.arg2 = arg2
        self.result = result
        
    def __str__(self):
        return f"({self.op}, {self.arg1}, {self.arg2}, {self.result})"
    
    def __repr__(self):
        return self.__str__()