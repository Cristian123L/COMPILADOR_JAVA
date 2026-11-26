from pathlib import Path
from frontend.app_gui import SynthesisSimulatorApp

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
<<<<<<< HEAD
    sample_file = base_dir / "samples" / "MasT.java"
=======
    sample_file = base_dir / "samples" / "01_programa_valido.java"
>>>>>>> fcf3ead725728c5564783a42393f120d0e691353
    app = SynthesisSimulatorApp(initial_file=sample_file)
    app.mainloop()