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

    #metadate for xml output file
    NSMAP = {
        None: "http://dataaccessioner.org/schema/dda-1-1",
        "premis": "info:lc/xmlns/premis-v2",
    }

    #creating a root  xml element for collection, and adding an accession element
    collection_el = LET.Element("collection", nsmap=NSMAP)
    accession_el = LET.SubElement(collection_el, "accession", number=accession_number)
    LET.SubElement(accession_el, "ingest_note").text = f"Transferred on {datetime.now().isoformat()}"

    for file_path in data_directory.rglob("*"):
        if not file_path.is_file():
            continue
        rel_path = file_path.relative_to(data_directory)
        dest_path = accession_folder / rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if move_files:
            shutil.move(str(file_path), str(dest_path))
        else:
            shutil.copy2(str(file_path), str(dest_path))

        stat_src = file_path.stat()
        os.utime(dest_path, (stat_src.st_atime, stat_src.st_mtime))

        # Preserve creation time on Windows
        if hasattr(os, "utime") and os.name == "nt":
            import ctypes
            from ctypes import wintypes

            FILE_WRITE_ATTRIBUTES = 0x0100
            handle = ctypes.windll.kernel32.CreateFileW(
                str(dest_path),
                FILE_WRITE_ATTRIBUTES,
                0,
                None,
                3,
                0,
                None
            )

            if handle != -1:
                # Convert Unix timestamp → Windows FILETIME
                def to_filetime(t):
                    return int((t * 10000000) + 116444736000000000)

                ctime = to_filetime(stat_src.st_ctime)
                ctime_low = ctime & 0xFFFFFFFF
                ctime_high = ctime >> 32

                class FILETIME(ctypes.Structure):
                    _fields_ = [("dwLowDateTime", wintypes.DWORD),
                                ("dwHighDateTime", wintypes.DWORD)]

                ft = FILETIME(ctime_low, ctime_high)
                ctypes.windll.kernel32.SetFileTime(handle, ctypes.byref(ft), None, None)
                ctypes.windll.kernel32.CloseHandle(handle)

        checksum = hashlib.md5(dest_path.read_bytes()).hexdigest()
        file_el = LET.SubElement(
            accession_el,
            "file",
            name=str(rel_path.as_posix()),
            size=str(dest_path.stat().st_size),
            MD5=checksum,
        )

        #metadata for xml output file
        #creates an object under each file
        premis_obj = LET.SubElement(file_el, "{info:lc/xmlns/premis-v2}object", nsmap=NSMAP)
        #assigns a UUID to each file to make it unique
        premis_id = LET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectIdentifier")
        LET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierType").text = "uuid"
        LET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierValue").text = str(uuid.uuid4())

    #writing to the xml output file
    xml_output_file = output_folder / f"{accession_number}.xml"
    LET.ElementTree(collection_el).write(str(xml_output_file), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    #if move files is selected, delete the original folder and subfolders from the input directory
    if move_files:
        for folder in sorted(data_directory.rglob("*"), reverse=True):
            try:
                if folder.is_dir() and not any(folder.iterdir()):
                    folder.rmdir()
            except Exception:
                # ignore folders that aren't empty or fail due to permissions
                pass  
        # optionally remove the top-level folder if it's empty
        try:
            if not any(data_directory.iterdir()):
                data_directory.rmdir()
        except Exception:
            pass
        
    return xml_output_file


# XSLT Processor
def run_xslt_processor(xml_input, xslt_file, output_file):
    xml_tree = LET.parse(str(xml_input))
    xslt_tree = LET.parse(str(xslt_file))
    transform = LET.XSLT(xslt_tree)
    result = transform(xml_tree)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(result))
    return output_file


# DA Fixity
def run_dafixity(xml_input, output_folder, accession_number, data_directory=None):
    output_folder = Path(output_folder)
    accession_folder = output_folder / accession_number
    data_directory = accession_folder if accession_folder.exists() else Path(data_directory)

    log_file = output_folder / f"dafixity_{accession_number}.log"
    csv_file = output_folder / f"dafixity_{accession_number}.csv"

    for h in logging.root.handlers[:]:
        logging.root.removeHandler(h)
    logging.basicConfig(level=logging.INFO, handlers=[logging.FileHandler(log_file, "w", encoding="utf-8")])

    tree = LET.parse(str(xml_input))
    root = tree.getroot()
    results = []

    for file_el in root.xpath("//default:file", namespaces={"default": "http://dataaccessioner.org/schema/dda-1-1"}):
        rel = Path(file_el.get("name"))
        file_path = data_directory / rel
        md5_stored = file_el.get("MD5")
        status = "OK"
        computed_md5 = ""
        error = ""
        try:
            if not file_path.exists():
                status = "MISSING"
                error = "File not found"
            else:
                computed_md5 = hashlib.md5(file_path.read_bytes()).hexdigest()
                if computed_md5 != md5_stored:
                    status = "MISMATCH"
        except Exception as e:
            status = "ERROR"
            error = str(e)

        results.append({
            "file_path": str(file_path),
            "stored_md5": md5_stored or "",
            "computed_md5": computed_md5 or "",
            "status": status,
            "error": error,
        })
        logging.info(f"[{status}] {file_path}")

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "stored_md5", "computed_md5", "status", "error"])
        writer.writeheader()
        writer.writerows(results)

    return csv_file, log_file
