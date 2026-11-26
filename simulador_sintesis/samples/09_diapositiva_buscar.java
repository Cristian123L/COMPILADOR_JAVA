package busca;
public  class  Buscar{
private int numeros[];
private int  ;
public int[] getNumeros(){
return numeros;}
public void setNumeros(int numeros){
this.numeros = numeros ;  }
public static void main(String [] args) {
int @var = 999;
Buscar obj = new Buscar(5)
System.out.println(obj.getNumeros());
}
// Ejemplo de las diapositivas de U4&U5 («Buscar», tabla de símbolos y tabla de errores).
// Las líneas 1-13 son las de la diapositiva; las anotaciones van al final para no moverlas.
// Tabla de símbolos de la maestra: busca 1, Buscar 2, numeros 3 (atributo), getNumeros 4,
// setNumeros 5, numeros 6 (parámetro: número NUEVO), this.numeros = ID3, numeros = ID6,
// args 7, @var sin número (error léxico), obj 8, new ID2, obj.getNumeros() = ID8 . ID4.
// La diapositiva marca 10 (@var), 4 (falta ID), 11 (falta ;) y 13 (falta }).
// Este compilador marca además 3, 5, 8 y 12, porque la GLC v7 no tiene reglas para
// arreglos, this ni llamadas como argumento.
