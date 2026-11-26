from pathlib import Path
from frontend.app_gui import SynthesisSimulatorApp

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    sample_file = base_dir / "samples" / "Uno.java"
    app = SynthesisSimulatorApp(initial_file=sample_file)
    app.mainloop()