// Inciso 2: NO hay main válido. Se BLOQUEAN los incisos 3 a 6.
// Prueba: corrige la firma a public static void main(String[] args) y todo se desbloquea.
package demo;
public class SinMain {
    int contador = 0;
    public static void main(int args) {
        contador = 1;
    }
}
