// Inciso 1: DEPURACIÓN. Se eliminan comentarios, tabulaciones, líneas vacías y espacios
// innecesarios; se conservan los saltos entre instrucciones y el contenido de las cadenas.
// Las llaves de cierre en líneas seguidas quedan juntas: }}
package demo;     // comentario al final de una línea


/* comentario de bloque
   en varias líneas */
public class Depuracion {
	public static void main(String[] args) {
		int   total   =   10 ;          // tabulaciones y espacios de más
		String url = "http://itsur.edu.mx";   // el // dentro de la cadena NO es comentario
		String nota = "  /* esto tampoco */  ";
		int otro = 5;;;;;;            // los ';' de más se quitan (queda uno solo)
		boolean mayor   =   total >= 5;   // solo queda el espacio entre palabras


		System.out.println(url);
	}
}
