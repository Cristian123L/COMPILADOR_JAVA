// Programa COMPLETAMENTE VÁLIDO (0 errores): package, import, atributos, un método con
// return, main, declaraciones, asignaciones, un objeto y println.
package tienda;

import utilerias.Calculadora;

public class Tienda {
    int inventario = 50;
    private String nombre = "Papeleria";

    public int calcular(int precio, int cantidad) {
        int total = (precio + 1) * cantidad;
        return total;
    }

    public static void main(String[] args) {
        int cantidad = 3;
        double precio = 19.99;
        float descuento = 0.5f;
        char letra = 'A';
        boolean activo = true;
        String texto = "ITSUR";
        Tienda tienda = new Tienda();
        int largo = texto.length();
        cantidad = cantidad + 2 * largo;
        activo = !activo;
        precio = precio * descuento;
        System.out.println(precio);
    }
}
