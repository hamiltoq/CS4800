from pathlib import Path
import hashlib
from datetime import datetime
from lxml import etree as LET
import uuid
import logging
import csv
import shutil
import os
import time

# Data Accessioner
def generate_data_accessioner_xml(data_directory, output_folder, accession_number, move_files=False):
    #converting input and output directory to paths
    data_directory = Path(data_directory)
    output_folder = Path(output_folder)
    
    #creating a folder inside the output directory for the input files to be copied/moved to
    accession_folder = output_folder / accession_number
    accession_folder.mkdir(parents=True, exist_ok=True)

    #metadata for xml output file
    NSMAP = {
        None: "http://dataaccessioner.org/schema/dda-1-1",
        "premis": "info:lc/xmlns/premis-v2",
    }

    #creating a root xml element for collection, and adding an accession element
    collection_el = LET.Element("collection", nsmap=NSMAP)
    accession_el = LET.SubElement(collection_el, "accession", number=accession_number)
    LET.SubElement(accession_el, "ingest_note").text = f"Transferred on {datetime.now().isoformat()}"

    #looping over every file in the input directory
    for file_path in data_directory.rglob("*"):
        
        #skip non-files
        if not file_path.is_file():
            continue

        #get original timestamps BEFORE moving/copying
        stat_src = file_path.stat()
        atime = stat_src.st_atime
        mtime = stat_src.st_mtime
        ctime = stat_src.st_ctime

        #compute the relative path
        rel_path = file_path.relative_to(data_directory)
        
        #create subfolders inside accession folder
        dest_path = accession_folder / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        #move or copy file
        if move_files:
            shutil.move(str(file_path), str(dest_path))
        else:
            shutil.copy2(str(file_path), str(dest_path))

        #restore access + modified time
        os.utime(dest_path, (atime, mtime))

        #restore creation time (Windows only)
        if os.name == "nt":
            try:
                import ctypes
                from ctypes import wintypes

                FILE_WRITE_ATTRIBUTES = 0x0100

                handle = ctypes.windll.kernel32.CreateFileW(
                    str(dest_path),
                    FILE_WRITE_ATTRIBUTES,
                    0,
                    None,
                    3,   # OPEN_EXISTING
                    0,
                    None
                )

                if handle != -1:
                    def to_filetime(t):
                        return int((t * 10000000) + 116444736000000000)

                    winctime = to_filetime(ctime)
                    
                    class FILETIME(ctypes.Structure):
                        _fields_ = [
                            ("dwLowDateTime", wintypes.DWORD),
                            ("dwHighDateTime", wintypes.DWORD)
                        ]

                    ft = FILETIME(winctime & 0xFFFFFFFF, winctime >> 32)

                    ctypes.windll.kernel32.SetFileTime(handle, ctypes.byref(ft), None, None)
                    ctypes.windll.kernel32.CloseHandle(handle)

            except Exception:
                #failure is safe — continue without breaking pipeline
                pass

        #compute checksum
        checksum = hashlib.md5(dest_path.read_bytes()).hexdigest()

        #add file entry to XML
        file_el = LET.SubElement(
            accession_el,
            "file",
            name=str(rel_path.as_posix()),
            size=str(dest_path.stat().st_size),
            MD5=checksum,
        )

        #add PREMIS metadata
        premis_obj = LET.SubElement(file_el, "{info:lc/xmlns/premis-v2}object", nsmap=NSMAP)
        premis_id = LET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectIdentifier")
        LET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierType").text = "uuid"
        LET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierValue").text = str(uuid.uuid4())

    #write XML file
    xml_output_file = output_folder / f"{accession_number}.xml"
    LET.ElementTree(collection_el).write(str(xml_output_file), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    #delete original directories if files were moved
    if move_files:
        for folder in sorted(data_directory.rglob("*"), reverse=True):
            try:
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
            except Exception:
                pass
            
        try:
            if not any(data_directory.iterdir()):
                data_directory.rmdir()
        except Exception:
            pass
        
    return xml_output_file


# XSLT Processor
def run_xslt_processor(xml_input, xslt_file, output_file):
    #parse the XML input into a tree structure
    xml_tree = LET.parse(str(xml_input))

    #parse the XSLT stylesheet into an XML tree
    xslt_tree = LET.parse(str(xslt_file))

    #convert the XSLT tree into a transform object
    transform = LET.XSLT(xslt_tree)

    #apply the XSLT transform to the XML input
    result = transform(xml_tree)

    #write the transformed content
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(result))
    return output_file


# DA Fixity
def run_fixity(xml_input, output_folder, accession_number, data_directory=None):
    #convert the output folder to a path
    output_folder = Path(output_folder)

    #builds the path to the accession folder that was created in Data Accessioner function
    accession_folder = output_folder / accession_number

    #if the accession folder exists, use that as data directory
    #otherwise use the original input directory 
    data_directory = accession_folder if accession_folder.exists() else Path(data_directory)

    #defines the log and CSV files and where they should be written
    log_file = output_folder / f"fixity_{accession_number}.log"
    csv_file = output_folder / f"fixity_{accession_number}.csv"

    #clears existing logging
    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)

    #configures logging to all messages are written to the log file
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(log_file, "w", encoding="utf-8")])

    #loads and parses the XML from Data Accessioner
    tree = LET.parse(str(xml_input))
    root = tree.getroot()

    #creating a list to add each file's checksum comparison result
    results = []

    #finds all of the file elements in the XML
    for file_el in root.xpath("//default:file", namespaces={"default": "http://dataaccessioner.org/schema/dda-1-1"}):
        #extracts the file's relative path
        rel = Path(file_el.get("name"))

        #constructs the full filesystem path to the actual file in the accession folder
        file_path = data_directory / rel

        #reads the checksum from the XML
        md5_stored = file_el.get("MD5")

        #initializes default values
        status = "OK"
        computed_md5 = ""
        error = ""

        try:
            #if the file is missing, mark MISSING
            if not file_path.exists():
                status = "MISSING"
                error = "File not found"

            
            else:
                #compute the new checksum, and compare it to the stored checksum
                computed_md5 = hashlib.md5(file_path.read_bytes()).hexdigest()

                #if the checksums are different, mark MISMATCH
                if computed_md5 != md5_stored:
                    status = "MISMATCH"

        #if an error occurs, mark ERROR
        except Exception as e:
            status = "ERROR"
            error = str(e)

        #save all of the information to the results list
        results.append({
            "file_path": str(file_path),
            "stored_md5": md5_stored or "",
            "computed_md5": computed_md5 or "",
            "status": status,
            "error": error,
        })

        #write a log entry to document the results
        logging.info(f"[{status}] {file_path}")

    #open the CSV and write the results
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "stored_md5", "computed_md5", "status", "error"])
        writer.writeheader()
        writer.writerows(results)

    return csv_file, log_file

