// Casteo (conversión explícita de tipo). No genera tokens ni se revisa con la GLC:
// solo el análisis semántico revisa si la conversión de tipos es posible.
package demo;
public class Casteo {
    public static void main(String[] args) {
        double real = 9.75;
        int entero = (int) real;
        int division = (int) (real / 2);
        char letra = (char) 65;
        double otro = (double) entero;
        byte chico = (byte) 300;
        int malo = real;
        boolean b = (boolean) entero;
        int n = (int) "texto";
    }
}
// Líneas 7 a 11: correctas (el casteo convierte el valor al tipo de la variable).
// Línea 12: incompatible (double a int SIN casteo).
// Líneas 13 y 14: error, no se puede castear int a boolean ni String a int.
