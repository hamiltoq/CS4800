from pathlib import Path
import hashlib
from datetime import datetime
from lxml import etree as LET
import uuid
import logging
import csv
import shutil

#Data Accessioner
def generate_data_accessioner_xml(data_directory, output_folder, accession_number, move_files=False):
    #metadata for xml output file
    NSMAP = {
        None: "http://dataaccessioner.org/schema/dda-1-1",
        "premis": "info:lc/xmlns/premis-v2",
        "da": "http://dataaccessioner.org/saxon-extension",
        "fits": "http://hul.harvard.edu/ois/xml/ns/fits/fits_output"
    }

    #converting input and output directory to paths
    data_directory = Path(data_directory)
    output_folder = Path(output_folder)

    #creating a folder inside the output directory for the input files to be copied/moved to
    accession_folder = output_folder / accession_number
    accession_folder.mkdir(parents=True, exist_ok=True)

    #creating a root  xml element for collection, and adding an accession element
    collection_el = LET.Element("collection", nsmap=NSMAP, name="")
    accession_el = LET.SubElement(collection_el, "accession", number=accession_number)

    #records the time and date for when the accession happened
    now = datetime.now()
    LET.SubElement(accession_el, "ingest_note").text = f"transferred on {now.strftime('%a %b %d %H:%M:%S %Z %Y')}"


    def add_folder(parent_el, folder_path, rel_path=Path()):
        #creates a folder element for each directory
        folder_el = LET.SubElement(parent_el, "folder", name=folder_path.name)
         
         #goes through each item in the input directory
        for item in folder_path.iterdir():
            if item.name.startswith('.'):
                continue
            relative_item_path = rel_path / item.name
            #if the item is a file, it calls the add_file function
            if item.is_file():
                add_file(folder_el, item, relative_item_path)
            #if the item is a subfolder, it calls itself recursively
            elif item.is_dir():
                add_folder(folder_el, item, relative_item_path)

    
    def add_file(parent_el, file_path, relative_item_path):
        #finds where to put the copied/moved files
        dest_path = accession_folder / relative_item_path
        #creates the subfolders
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        #copy or move file
        if move_files:
            shutil.move(str(file_path), str(dest_path))
        else:
            shutil.copy2(str(file_path), str(dest_path))

        #gets files size and timestamps
        stat = dest_path.stat()
        #computes the checksum
        checksum = hashlib.md5(dest_path.read_bytes()).hexdigest()

        #adds a file xml element with the name, timestamp, size, and checksum
        file_el = LET.SubElement(
            parent_el, "file",
            name=file_path.name,
            last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            size=str(stat.st_size),
            MD5=checksum
        )

        #metadata for xml output file
        #creates an object under each file
        premis_obj = LET.SubElement(file_el, "{info:lc/xmlns/premis-v2}object", nsmap=NSMAP)
        #assigns a UUID to each file to make it unique
        premis_id = LET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectIdentifier")
        LET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierType").text = "uuid"
        LET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierValue").text = str(uuid.uuid4())

        #stores checksum infor
        premis_char = LET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectCharacteristics")
        fixity = LET.SubElement(premis_char, "{info:lc/xmlns/premis-v2}fixity")
        LET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigestAlgorithm").text = "MD5"
        LET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigest").text = checksum
        LET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigestOriginator").text = "Python DataAccessioner Script"
        LET.SubElement(premis_char, "{info:lc/xmlns/premis-v2}size").text = str(stat.st_size)
        LET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}originalName").text = file_path.name

    #starting the recursive scan
    add_folder(accession_el, data_directory)

    #writing to the xml output file
    xml_output_file = output_folder / f"{accession_number}.xml"
    LET.ElementTree(collection_el).write(str(xml_output_file), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    return xml_output_file


#XSLT Processor
def run_xslt_processor(xml_input, xslt_file, output_file):
    xml_tree = LET.parse(str(xml_input))
    xslt_tree = LET.parse(str(xslt_file))
    transform = LET.XSLT(xslt_tree)
    result = transform(xml_tree)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(str(result))

    return output_file


#DA Fixity
def run_dafixity(xml_input, output_folder, accession_number, data_directory=None):
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    if data_directory:
        data_directory = Path(data_directory)

    log_file = output_folder / f"dafixity_{accession_number}.log"
    csv_file = output_folder / f"dafixity_{accession_number}.csv"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_file, mode="w", encoding="utf-8")]
    )

    logging.info("--- Starting Checksum Verification ---")
    logging.info(f"Input XML: {xml_input}")
    logging.info(f"Output CSV: {csv_file}")

    results = []

    try:
        tree = LET.parse(str(xml_input))
        root = tree.getroot()
    except Exception as e:
        logging.error(f"Failed to parse XML file: {e}")
        return None

    for file_el in root.xpath("//default:file", namespaces={"default": "http://dataaccessioner.org/schema/dda-1-1"}):
        file_name = file_el.get("name")
        md5_stored = file_el.get("MD5")

        parent_folders = []
        parent = file_el.getparent()
        while parent is not None and parent.tag.endswith("folder"):
            parent_folders.insert(0, parent.get("name"))
            parent = parent.getparent()

        folder_path = Path(*parent_folders)
        if data_directory:
            file_path = data_directory / folder_path / file_name
        else:
            file_path = folder_path / file_name

        md5_new = None
        status = "OK"
        error_message = ""

        try:
            if not file_path.exists():
                status = "MISSING"
                error_message = "File not found"
            else:
                md5_new = hashlib.md5(file_path.read_bytes()).hexdigest()
                if md5_new != md5_stored:
                    status = "MISMATCH"
        except Exception as e:
            status = "ERROR"
            error_message = str(e)

        results.append({
            "file_path": str(file_path),
            "stored_md5": md5_stored or "",
            "computed_md5": md5_new or "",
            "status": status,
            "error": error_message
        })

        logging.info(f"[{status}] {file_path}")

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "stored_md5", "computed_md5", "status", "error"])
        writer.writeheader()
        writer.writerows(results)

    logging.info("--- Checksum Verification Complete ---")
    logging.info(f"Results saved to {csv_file}")
    return csv_file, log_file
