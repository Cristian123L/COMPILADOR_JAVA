public class PruebaCompleta {
    double pi = 3.1415;
    float uno = 1.45f;
    int constanteNoUsada = 99 * 2;

    public double calculadora_cientifica(double radio) {
        double pi = 3.14159264;
        double sumaConst = 20 + 5;
        double a = pi * radio + 0;
        double repetida = pi * radio;
        return a + repetida + sumaConst;
    }

    public static void main(String[] args) {
        System.out.println(new PruebaCompleta().calculadora_cientifica(10));
    }
}