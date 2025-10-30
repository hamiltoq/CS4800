from tkinter import *
from tkinter import ttk
from tkinter import filedialog as fd
from tkinter.messagebox import showinfo

window = Tk()
window.geometry("420x420")
window.title("Automated Archival Process")

labelDA = Label(window, text="Data Accessioner", font=("Arial", 15, "bold"))
labelDA.pack()

labelXSLT = Label(window, text="XSLT Processor", font=("Arial", 15, "bold"))
labelXSLT.pack()

labelDAF = Label(window, text="DAFixity", font=("Arial", 15, "bold"))
labelDAF.pack()

def select_file():
    filetypes = (
        ('All files', '*.*'),
        ('Text files', '*.txt')
    )

    filename = fd.askopenfilename(
        title='Open a file',
        initialdir='/',
        filetypes=filetypes)

    showinfo(
        title='Selected File',
        message=filename
    )


open_button = ttk.Button(
    window,
    text='Choose File',
    command=select_file
)

open_button.pack(expand=True)


window.mainloop()

