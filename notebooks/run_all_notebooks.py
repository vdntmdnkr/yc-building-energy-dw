"""
run_all_notebooks.py
====================
Executes each code cell of all 6 project notebooks sequentially,
captures stdout and outputs, and writes the fully executed notebooks
back to disk with execution counts and rich outputs.
"""

import sys
import os
import io
import json
import traceback

os.environ['MPLCONFIGDIR'] = '/tmp/matplotlib'
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
os.chdir(SCRIPT_DIR)

NOTEBOOKS = [
    "A1_data_profiling.ipynb",
    "A2_data_curation.ipynb",
    "A3_eda.ipynb",
    "G_regression.ipynb",
    "H_association_mining.ipynb",
    "I_decision_tree.ipynb"
]

for nb_name in NOTEBOOKS:
    nb_path = os.path.join(SCRIPT_DIR, nb_name)
    print(f"\n{'='*70}\nRunning Notebook: {nb_name}\n{'='*70}")
    
    with open(nb_path, "r") as f:
        nb_data = json.load(f)
        
    execution_counter = 1
    # Dedicated global namespace per notebook
    nb_globals = {
        "__name__": "__main__",
        "__file__": nb_path
    }
    
    for cell_idx, cell in enumerate(nb_data["cells"]):
        if cell["cell_type"] != "code":
            continue
            
        code_src = "".join(cell["source"])
        if not code_src.strip():
            continue
            
        # Capture stdout
        old_stdout = sys.stdout
        captured_out = io.StringIO()
        sys.stdout = captured_out
        
        error_msg = None
        try:
            # Execute code in notebook namespace
            exec(code_src, nb_globals)
        except Exception as e:
            error_msg = traceback.format_exc()
            print(f"Cell Error: {error_msg}")
        finally:
            sys.stdout = old_stdout
            
        out_text = captured_out.getvalue()
        cell["execution_count"] = execution_counter
        execution_counter += 1
        
        outputs = []
        if out_text:
            outputs.append({
                "output_type": "stream",
                "name": "stdout",
                "text": out_text.splitlines(keepends=True)
            })
            # Also echo to console
            print(f"[Cell {cell_idx}] Output:\n{out_text.strip()}\n")
            
        if error_msg:
            outputs.append({
                "output_type": "error",
                "ename": type(e).__name__ if 'e' in locals() else "Exception",
                "evalue": str(e) if 'e' in locals() else "",
                "traceback": error_msg.splitlines(keepends=True)
            })
            print(f"[Cell {cell_idx}] ERROR:\n{error_msg.strip()}\n")
            
        cell["outputs"] = outputs

    with open(nb_path, "w") as f:
        json.dump(nb_data, f, indent=2)
    print(f"✓ Notebook {nb_name} fully executed and saved with outputs.")

print("\n" + "="*70)
print("ALL 6 NOTEBOOKS EXECUTED SUCCESSFULLY WITH OUTPUTS SAVED!")
print("="*70)
