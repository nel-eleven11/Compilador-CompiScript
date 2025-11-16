// Helpers "declarados" en el lenguaje; la implementacion real la hace el backend MIPS.
function toString(x: integer): string {
  return "";
}

// Clase base
class Persona {
  let nombre: string;
  let edad: integer;
  let color: string;

  function constructor(nombre: string, edad: integer) {
    this.nombre = nombre;
    this.edad = edad;
    this.color = "rojo";
  }

  function saludar(): string {
    return "Hola, mi nombre es " + this.nombre;
  }

  function incrementarEdad(anos: integer): string {
    this.edad = this.edad + anos;
    return "Ahora tengo " + toString(this.edad) + " anios.";
  }
}

// Programa principal
let nombre: string = "Nelson";
let nelson: Estudiante = new Persona(nombre, 22);
print(nelson.saludar());

