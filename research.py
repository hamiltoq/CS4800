from pathlib import Path
import hashlib
from datetime import datetime
import xml.etree.ElementTree as ET
from lxml import etree as LET
from lxml import etree as ET
import uuid
import logging
import csv
import os
import shutil

def generate_data_accessioner_xml(data_directory, output_folder, accession_number):
    # Setup XML namespace (same as Data Accessioner)
    NSMAP = {
        None: "http://dataaccessioner.org/schema/dda-1-1",
        "premis": "info:lc/xmlns/premis-v2",
        "da": "http://dataaccessioner.org/saxon-extension",
        "fits": "http://hul.harvard.edu/ois/xml/ns/fits/fits_output"
    }

    data_directory = Path(data_directory)
    output_folder = Path(output_folder)
    
    # Create subfolder named after the accession number (for copied files)
    accession_folder = output_folder / accession_number
    accession_folder.mkdir(parents=True, exist_ok=True)

    # Create XML structure
    collection_el = ET.Element("collection", nsmap=NSMAP, name="")
    accession_el = ET.SubElement(collection_el, "accession", number=accession_number)

    # Add ingest note
    now = datetime.now()
    ET.SubElement(accession_el, "ingest_note").text = f"transferred on {now.strftime('%a %b %d %H:%M:%S %Z %Y')}"

    # Recursive folder processing
    def add_folder(parent_el, folder_path, rel_path=Path()):
        folder_el = ET.SubElement(parent_el, "folder", name=folder_path.name)
        for item in folder_path.iterdir():
            if item.name.startswith('.'):
                continue  # skip hidden files
            relative_item_path = rel_path / item.name
            if item.is_file():
                add_file(folder_el, item, relative_item_path)
            elif item.is_dir():
                add_folder(folder_el, item, relative_item_path)

    # Copy files and add XML entries
    def add_file(parent_el, file_path, relative_item_path):
        dest_path = accession_folder / relative_item_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest_path)

        stat = file_path.stat()
        checksum = hashlib.md5(file_path.read_bytes()).hexdigest()

        file_el = ET.SubElement(
            parent_el,
            "file",
            name=file_path.name,
            last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            size=str(stat.st_size),
            MD5=checksum
        )

        # Add PREMIS metadata
        premis_obj = ET.SubElement(file_el, "{info:lc/xmlns/premis-v2}object", nsmap=NSMAP)
        premis_id = ET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectIdentifier")
        ET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierType").text = "uuid"
        ET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierValue").text = str(uuid.uuid4())

        premis_char = ET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectCharacteristics")
        fixity = ET.SubElement(premis_char, "{info:lc/xmlns/premis-v2}fixity")
        ET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigestAlgorithm").text = "MD5"
        ET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigest").text = checksum
        ET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigestOriginator").text = "Python DataAccessioner Script"
        ET.SubElement(premis_char, "{info:lc/xmlns/premis-v2}size").text = str(stat.st_size)
        ET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}originalName").text = file_path.name

    # Start folder recursion
    add_folder(accession_el, data_directory)

    # XML file goes in the *main* output folder (not inside accession folder)
    xml_output_file = output_folder / f"{accession_number}.xml"
    ET.ElementTree(collection_el).write(str(xml_output_file), encoding="UTF-8", xml_declaration=True, pretty_print=True)

    print(f"Data Accessioner complete!")
    print(f"Files copied to: {accession_folder}")
    print(f"XML saved to: {xml_output_file}")

    return xml_output_file


#xml_input: the output from data accessioner
#xslt_file: the xslt stylesheet (for CSV or HTML)
#output_file: where the output will be saved
def run_xslt_processor(xml_input, xslt_file, output_file):
    #loading the XML input and stylesheet
    xml_tree = LET.parse(str(xml_input))
    xslt_tree = LET.parse(str(xslt_file))
    transform = LET.XSLT(xslt_tree)
    result = transform(xml_tree)

    #converting the result to a string then writing it to the output file
    result_str = str(result)
    with open(output_file, "w", encoding = "utf-8") as f:
        f.write(result_str)
    
    return output_file
    

def run_dafixity(xml_input, output_folder, accession_number, data_directory=None):
    output_folder = Path(output_folder)
    output_folder.mkdir(parents=True, exist_ok=True)
    if data_directory:
        data_directory = Path(data_directory)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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
            base_name = data_directory.name
            if parent_folders and parent_folders[0] == base_name:
                file_path = data_directory.parent / folder_path / file_name
            else:
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
        if error_message:
            logging.warning(f"  {error_message}")

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["file_path", "stored_md5", "computed_md5", "status", "error"])
        writer.writeheader()
        writer.writerows(results)

    logging.info("--- Checksum Verification Complete ---")
    logging.info(f"Results saved to {csv_file}")
    return csv_file, log_file



if __name__ == "__main__":
    #Data Accessioner
    folder = "output"
    accession_number = "2025-101"
    data = Path(r"C:\Users\lib-hamiltoq\Downloads\UA2020-53-20250917T183847Z-1-001\UA2020-53\Hal Wohl")

    xml_report = generate_data_accessioner_xml(data, folder, accession_number)

    print("\n-----------------------------------------------\n")

    
    #XSLT Processor
    script_dir = Path(__file__).parent
    xslt_csv = script_dir / "files.csv.xslt"
    xslt_html = script_dir / "files.html.xslt"
    csv_transformed = xml_report.with_name(xml_report.stem + "_files.csv")
    html_transformed = xml_report.with_name(xml_report.stem + "_files.html")

    run_xslt_processor(xml_report, xslt_csv, csv_transformed)
    run_xslt_processor(xml_report, xslt_html, html_transformed)

    print("XSLT Processor complete!")
    print("CSV transform saved to:", csv_transformed)
    print("HTML transform saved to:", html_transformed)

    print("\n-----------------------------------------------\n")


    #DAFixity
    fixity_csv, fixity_log = run_dafixity(xml_report, folder, accession_number, data)

    print("DAFixity complete!")
    print("Fixity CSV: ", fixity_csv)
    print("Fixity log: ", fixity_log)

