// Inciso 3: TABLA DE SÍMBOLOS (criterios de U4&U5).
//  - escuela 1, Alumno 2, nombre 3 (atributo), promedio 4 (atributo), setNombre 5,
//    nombre 6 (parámetro: número NUEVO aunque exista el atributo 3), args 7, a 8, total 9.
//  - Un uso se escribe como enlace: nombre = ID6 dentro de setNombre.
//  - System, out y println no se numeran (son nombres de Java).
//  - int total; repetido en el mismo ámbito: ID = XX (no consume número).
package escuela;
public class Alumno {
    String nombre;
    double promedio = 9.5;
    public void setNombre(String nombre) {
        System.out.println(nombre);
    }
    public static void main(String[] args) {
        Alumno a = new Alumno();
        int total = 3;
        int total = 4;
        System.out.println(total);
    }
}
