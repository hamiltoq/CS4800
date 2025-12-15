import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from cs4800 import generate_data_accessioner_xml, run_xslt_processor, run_fixity

def run_pipeline():
    #gets all of the inputs from the GUI
    data_dir = input_dir_var.get()
    out_dir = output_dir_var.get()
    accession_number = accession_var.get().strip()
    move_files = move_var.get()

    #makes sure all of the inputs are filled in
    if not data_dir or not out_dir or not accession_number:
        messagebox.showerror("Missing Information", "Please fill in all fields before running.")
        return

    try:
        #Data Accessioner
        xml_report = generate_data_accessioner_xml(data_dir, out_dir, accession_number, move_files)

        #XSLT Processor
        script_dir = Path(__file__).parent
        xslt_csv = script_dir / "files.csv.xslt"
        xslt_html = script_dir / "files.html.xslt"

        csv_transformed = Path(out_dir) / f"{accession_number}_files.csv"
        html_transformed = Path(out_dir) / f"{accession_number}_files.html"

        run_xslt_processor(xml_report, xslt_csv, csv_transformed)
        run_xslt_processor(xml_report, xslt_html, html_transformed)

        #Fixity
        fixity_csv, fixity_log = run_fixity(xml_report, out_dir, accession_number, Path(data_dir))

        #message box that shows up when the pipeline is complete
        messagebox.showinfo(
            "Pipeline Complete",
            f"Data Accessioner complete!\n"
            f"XML: {xml_report}\n\n"
            f"XSLT Processor complete!\n"
            f"CSV: {csv_transformed}\nHTML: {html_transformed}\n\n"
            f"Fixity complete!\n"
            f"Fixity CSV: {fixity_csv}\nFixity Log: {fixity_log}"
        )

    #catches errors
    except Exception as e:
        messagebox.showerror("Pipeline Error", f"An error occurred:\n\n{e}")

#creates the main GUI window
root = tk.Tk()
root.title("Archival Pipeline")
root.geometry("550x300")

#defines variables that store data in the GUI
input_dir_var = tk.StringVar()
output_dir_var = tk.StringVar()
accession_var = tk.StringVar()
move_var = tk.BooleanVar()

#creates input directory text label, text box, and Browse button to select input directory
tk.Label(root, text="Input Directory:").grid(row=0, column=0, sticky="e", padx=10, pady=5)
tk.Entry(root, textvariable=input_dir_var, width=40).grid(row=0, column=1, pady=5)
tk.Button(root, text="Browse", command=lambda: input_dir_var.set(filedialog.askdirectory())).grid(row=0, column=2, padx=5)

#creates output directory label, text box, and Browse button to select output directory
tk.Label(root, text="Output Directory:").grid(row=1, column=0, sticky="e", padx=10, pady=5)
tk.Entry(root, textvariable=output_dir_var, width=40).grid(row=1, column=1, pady=5)
tk.Button(root, text="Browse", command=lambda: output_dir_var.set(filedialog.askdirectory())).grid(row=1, column=2, padx=5)

#creates accession number label and text box
tk.Label(root, text="Accession Number:").grid(row=2, column=0, sticky="e", padx=10, pady=5)
tk.Entry(root, textvariable=accession_var, width=25).grid(row=2, column=1, pady=5)

#creates check box for move/copy files
tk.Checkbutton(root, text="Move files instead of copy", variable=move_var).grid(row=3, column=1, sticky="w", pady=5)

#creates run pipeline button
tk.Button(root, text="Run Pipeline", command=run_pipeline, bg="#4CAF50", fg="white", width=15).grid(row=5, column=1, pady=20)

root.mainloop()

