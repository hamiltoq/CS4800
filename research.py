from pathlib import Path
import hashlib
from datetime import datetime
import xml.etree.ElementTree as ET
from lxml import etree as LET
from lxml import etree as ET
import uuid
import logging
import csv

#data_directory: folder to be accessioned
#output_folder: where the XML output will go            
def generate_data_accessioner_xml(data_directory, output_folder, accession_number):
    #setup XML namespace from Data Accessioner
    NSMAP = {None: "http://dataaccessioner.org/schema/dda-1-1",
            "premis": "info:lc/xmlns/premis-v2",
            "da": "http://dataaccessioner.org/saxon-extension",
            "fits": "http://hul.harvard.edu/ois/xml/ns/fits/fits_output"}
    
    #building root collection and accession elements
    collection_el = ET.Element("collection", nsmap = NSMAP, name = "")
    accession_el = ET.SubElement(collection_el, "accession", number = accession_number)

    #adding information for when the data was processed
    now = datetime.now()
    ET.SubElement(accession_el, "ingest_note").text = f"transferred on {now.strftime('%a %b %d %H:%M:%S %Z %Y')}"

    #recursive function that goes through each subdirectory in the data
    def add_folder(parent_el, folder_path):
        #creates a folder element for each subdirectory
        folder_el = ET.SubElement(parent_el, "folder", name = folder_path.name)
        for item in folder_path.iterdir():
            if item.is_file():
                add_file(folder_el, item)
            elif item.is_dir():
                add_folder(folder_el, item)

    #adding each file to the XML output
    def add_file(parent_el, file_path):
        #gather file stats, calculates checksum, and adds the file element to the XML
        stat = file_path.stat()
        checksum = hashlib.md5(file_path.read_bytes()).hexdigest()
        file_el = ET.SubElement(parent_el, "file", name = file_path.name,
                                last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                size = str(stat.st_size), MD5 = checksum)

        #adding identifiers to the XML file
        premis_obj = ET.SubElement(file_el, "{info:lc/xmlns/premis-v2}object", nsmap = NSMAP)
        premis_id = ET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectIdentifier")
        ET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierType").text = "uuid"
        ET.SubElement(premis_id, "{info:lc/xmlns/premis-v2}objectIdentifierValue").text = str(uuid.uuid4())
        
        #adding checksum information
        premis_char = ET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}objectCharacteristics")
        fixity = ET.SubElement(premis_char, "{info:lc/xmlns/premis-v2}fixity")
        ET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigestAlgorithm").text = "MD5"
        ET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigest").text = checksum
        ET.SubElement(fixity, "{info:lc/xmlns/premis-v2}messageDigestOriginator").text = "Python DataAccessioner Script"
        ET.SubElement(premis_char, "{info:lc/xmlns/premis-v2}size").text = str(stat.st_size)
        ET.SubElement(premis_obj, "{info:lc/xmlns/premis-v2}originalName").text = file_path.name

    #run recursive folder scanning
    add_folder(accession_el, Path(data_directory))

    #creating and writing the complete XML tree to the output file
    tree = ET.ElementTree(collection_el)
    output_file = Path(output_folder) / f"{accession_number}.xml"
    Path(output_folder).mkdir(parents=True, exist_ok=True)
    tree.write(str(output_file), encoding = "UTF-8", xml_declaration = True, pretty_print = True)
    
    print(f"Data Accessioner complete! XML in {output_file}")
    return output_file


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
    

def run_dafixity(xml_input, output_folder):
    outout_folder = Path(output_folder)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_folder / f"dafixity_{timestamp}.log"
    csv_file = output_folder / f"dafixity_{timestamp}.csv"

    logging.basicConfig(level = logging.INFO, 
                        format = "%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.FileHandler(log_file, mode="w", encoding="utf-8"),
                                    logging.StreamHandler()])
    
    logging.info("--- Starting Checksum Verification ---")
    logging.info(f"Input XML: {xml_input}")
    logging.info(f"Output: {csv_file}")

    results = []

    try:
        tree = LET.parse9str(xml_input)
        root = tree.getroot()
    except Exception as e:
        logging.error(f"Failed to parse XML file: {e}")
        return None

    for file_el in root.xpath("//default:file", namespaces = {"default":"http://dataaccessioner.org/schema/dda-1-1"}):
        file_name = file_el.get("name")
        md5_stored = file_el.get("MD5")
        directory = file_el.get("directory") or "Unknown"

        parent_folders = []
        parent = file_el.getparent()
        while parent is not None and parent.tag.endswith("folder"):
            parent_folders.insert(0, parent.get("name"))
            parent = parent.getparent()
        
        folder_path = Path(*parent_folders)
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
        
        results.append({"file_path": str(file_path),
                        "stored_md5": md5_new if md5_new else "",
                        "status": status,
                        "error": error_message})
        
        logging.info(f"[{status}] {file_path}")
        if error_message:
            logging.warning(f"  {error_message}")
    
    with open(csv_file, "w", newline = "", encoding = "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames = ["file+path", "stored_md5", "computer_md5", "status", "error"])
        writer.writeheader()
        writer.writerows(results)

    logging.info("--- Checksum Verification Complete ---")
    logging.info(f"Results saved to {csv_file}")
    return csv_file, log_file


if __name__ == "__main__":
    #Data Accessioner
    folder = "output"
    accession_number = "2025-101"
    data = Path(r"C:\Users\quinn\Downloads\Hal Wohl-20251022T164146Z-1-001\Hal Wohl")

    xml_report = generate_data_accessioner_xml(data, folder, accession_number)

    print("\n-----------------------------------------------\n")

    
    #XSLT Processor
    xslt_csv = Path(r"C:\Users\Public\Desktop\XSLTProcessor-1.2\xslt\files.csv.xslt")
    xslt_html = Path(r"C:\Users\Public\Desktop\XSLTProcessor-1.2\xslt\files.html.xslt")
    csv_transformed = xml_report.with_name(xml_report.stem + "_files.csv")
    html_transformed = xml_report.with_name(xml_report.stem + "_files.html")

    run_xslt_processor(xml_report, xslt_csv, csv_transformed)
    run_xslt_processor(xml_report, xslt_html, html_transformed)

    print("XSLT Processor complete!")
    print("CSV transform saved to:", csv_transformed)
    print("HTML transform saved to:", html_transformed)

    print("\n-----------------------------------------------\n")


    #DAFixity
    fixity_csv, fixity_log = run_dafixity(xml_report, folder)

    print("DAFixity complete!")
    print("Fixity CSV: ", fixity_csv)
    print("Fixity log: ", fixity_log)

    

