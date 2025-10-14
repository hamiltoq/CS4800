from pathlib import Path
import hashlib
import csv
from datetime import datetime
import xml.etree.ElementTree as ET
from lxml import etree as LET
from lxml import etree as ET
import getpass
import uuid
            
def generate_data_accessioner_xml(data_directory, output_folder, accession_number):
    NSMAP = {None: "http://dataaccessioner.org/schema/dda-1-1",
            "premis": "info:lc/xmlns/premis-v2",
            "da": "http://dataaccessioner.org/saxon-extension",
            "fits": "http://hul.harvard.edu/ois/xml/ns/fits/fits_output"}
    collection_el = ET.Element("collection", nsmap = NSMAP, name = "")
    accession_el = ET.SubElement(collection_el, "accession", number = accession_number)

    now = datetime.now()
    ET.SubElement(accession_el, "ingest_note").text = f"transferred on {now.strftime('%a %b %d %H:%M:%S %Z %Y')}"
    ET.SubElement(accession_el, "ingest_time").text = "00:00:00.00000"

    def add_folder(parent_el, folder_path):
        folder_el = ET.SubElement(parent_el, "folder", name = folder_path.name)
        for item in folder_path.iterdir():
            if item.is_file():
                add_file(folder_el, item)
            elif item.is_dir():
                add_folder(folder_el, item)

    def add_file(parent_el, file_path):
        stat = file_path.stat()
        checksum = hashlib.md5(file_path.read_bytes()).hexdigest()
        file_el = ET.SubElement(parent_el, "file", name = file_path.name,
                                last_modified = datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                size = str(stat.st_size), MD5 = checksum)

        premis_obj = ET.SubElement(file_el, "{info:lc/xmlns/premis-v2}object", nsmap = NSMAP)

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

    add_folder(accession_el, Path(data_directory))

    tree = ET.ElementTree(collection_el)
    output_file = Path(output_folder) / f"{accession_number}.xml"
    tree.write(str(output_file), encoding = "UTF-8", xml_declaration = True, pretty_print = True)
    
    print(f"Data Accessioner complete! XML in {output_file}")
    return output_file

def run_xslt_processor(xml_input, xslt_file, output_file):
    xml_tree = LET.parse(str(xml_input))
    xslt_tree = LET.parse(str(xslt_file))
    transform = LET.XSLT(xslt_tree)
    result = transform(xml_tree)

    result_str = str(result)

    with open(output_file, "w", encoding = "utf-8") as f:
        f.write(result_str)
    
    return output_file
    

#def run_dafixity():


if __name__ == "__main__":
    #Data Accessioner
    folder = "output"
    accession_number = "2025-101"
    data = Path(r"M:\Working Groups\DSU\Art on Campus\UNI Art Exhibitions 2011-2012\Pamphlets")

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

    