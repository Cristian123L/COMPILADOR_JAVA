// Inciso 2: falta 'package'. La GLC v7 lo exige (JAVA ::= DPACKAGE IMPORTS CLASE):
// es un error sintáctico, pero NO bloquea porque el main sí es válido.
public class SinPackage {
    public static void main(String[] args) {
        int x = 5;
        System.out.println(x);
    }
}
