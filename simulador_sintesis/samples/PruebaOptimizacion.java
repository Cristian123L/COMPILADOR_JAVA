public class PruebaOptimizacion {
    public static void main(String[] args) {
        int base = 10;
        int altura = 5;
        int sumaConst = 20 + 5;
        int area = base * altura + 0;
        int repetida = base * altura;
        int muerta = 99 * 2;
        int resultado = area + repetida + sumaConst;
        System.out.println(resultado);
    }
}