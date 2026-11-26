// Inciso 5: CORRESPONDENCIA DE TIPOS y lista de asignaciones correctas.
package demo;
public class Tipos {
    public static void main(String[] args) {
        int entero = 10;
        double real = entero;
        float flotante = 2.5f;
        char letra = 'A';
        boolean bandera = true;
        String texto = "Hola";
        byte chico = 100;
        int malo = 2.5;
        boolean otra = 1;
        String cadena = 'x';
        char c = texto;
        int a;
        int a = 0;
        texto = texto + entero;
        real = flotante * 2;
    }
}
// Correctas: líneas 5-11, 18 y 19 (int->double y float->double son ampliaciones).
// Incompatibles: 12 (double a int), 13 (int a boolean), 14 (char a String), 15 (String a char).
// Línea 17: REDECLARACIÓN de 'a' (error semántico). Sus tipos sí corresponden (int ← int),
// por eso no se muestra como incompatibilidad, pero tampoco se lista como correcta.
