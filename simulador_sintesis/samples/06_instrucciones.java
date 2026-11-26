// Inciso 4: instrucciones que CUMPLEN y que NO cumplen la GLC.
package demo;
public class Instrucciones {
    public static void main(String[] args) {
        int a = 5;
        int b = 10
        int c = a + ;
        int d = (a + b;
        System.out.println(a)
        System.out.println(b);
        a = b * 2;
        int e = a, f = b;
        String s = "fin";
    }
}
// Línea  6: falta ';' al final (el error se marca en la línea 6, la 7 se analiza normal).
// Línea  7: expresión incompleta (falta un valor después de '+').
// Línea  8: delimitador incorrecto (falta ')').
// Línea  9: println sin ';'. La línea 10 (con ';') sí cumple.
// Línea 12: la GLC no permite declarar variables en lista.
