// Inciso 6: TABLA DE ERRORES con los tres tipos y sus colores.
//   Verde = léxico, rojo = sintáctico, azul = semántico.
package demo;
public class Errores {
    public static void main(String[] args) {
        int precio = 5;
        int #total = 3;
        String s = "sin cerrar;
        int x = 10
        int y = x + 1;
        boolean b = 25;
        z = 4;
        int precio = 7;
    }
}
// Línea  7: léxico ('#total' no es un identificador válido).
// Línea  8: léxico (cadena sin cerrar).
// Línea  9: sintáctico (falta ';').
// Línea 11: semántico (int a boolean).
// Línea 12: semántico ('z' no está declarada).
// Línea 13: semántico (redeclaración de 'precio').
