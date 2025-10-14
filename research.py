from pathlib import Path
import hashlib
import csv
import datetime
import xml.etree.ElementTree as ET
from lxml import etree as LET
import getpass
import uuid

def checksum_for_file(file_path: Path) -> str:
    hasher = hashlib.md5()
    
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
        return hasher.hexdigest()

def build_xml(parent, folder_path: Path):
    folder_el = ET.SubElement(
        parent, "folder", {"name": folder_path.name, "last_modified": datetime.fromtimestamp(folder_path.stat().st_mtime).isoformat(),},)
    
    for path in sorted(folder_path.iterdir()):
        if path.is_dir():
            build_xml(folder_el, path)
        elif path.is_file():
            checksum = checksum_for_file(path)
            attrs = {"name": path.name, "last_modified": datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                     "size": str(path.stat().st_size), "MD5": checksum,}
            if path.name.startswith("."):
                attrs["hidden"] = "true"

            file_el = ET.SubElement(folder_el, "file", attrs)
            
def run_data_accessioner(data_directory, output_folder, accession_number):
    data_directory = Path(data_directory)
    output_directory = Path(output_folder)
    output_directory.mkdir(parents = True, exist_ok = True)

    all_reports = []

    all_directories = [data_directory] + [p for p in data_directory.rglob("*") if p.is_dir()]

    for subfolder in all_directories:
        if subfolder.is_dir():
            relative_subfolder = subfolder.relative_to(data_directory)


            report_xml = output_directory / f"{accession_number}.xml"
            report_csv = output_directory / f"{accession_number}.csv"

            root = ET.Element("dataaccessioner")
            rows = []

            for path in subfolder.rglob("*"):
                if path.is_file():
                    checksum = hashlib.md5(path.read_bytes()).hexdigest()

                    file_el = ET.SubElement(root, "file")
                    ET.SubElement(file_el, "name").text = path.name
                    ET.SubElement(file_el, "checksum").text = checksum
                    ET.SubElement(file_el, "directory").text = str(path.parent)

                    rows.append({"directory path": str(path.parent), "filename": path.name, "checksum": checksum})
            if rows:
                #write XML
                tree = ET.ElementTree(root)
                tree.write(report_xml, encoding="utf-8", xml_declaration = True)

            #write CSV
            with open(report_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames = ["directory path", "filename", "checksum"])
                writer.writeheader()
                writer.writerows(rows)

            all_reports.append((report_xml, report_csv))


    print("Data Accessioner complete. Reports in", output_directory)
    return all_reports, output_directory

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
    data = Path(r"M:\Working Groups\DSU\Art on Campus\Exhibitions\2011-2012\Pamphlets")

    all_reports, out_dir = run_data_accessioner(data, folder, accession_number)

    print("Output directory:", out_dir)

    print("\n-----------------------------------------------\n")

    
    #XSLT Processor
    xslt_csv = Path(r"C:\Users\Public\Desktop\XSLTProcessor-1.2\xslt\files.csv.xslt")
    xslt_html = Path(r"C:\Users\Public\Desktop\XSLTProcessor-1.2\xslt\files.html.xslt")
    for xml_report, csv_report in all_reports:
        csv_transformed = xml_report.with_name(xml_report.stem + "xslt.csv")
        html_transformed = xml_report.with_name(xml_report.stem + "xslt.html")

        run_xslt_processor(xml_report, xslt_csv, csv_transformed)
        run_xslt_processor(xml_report, xslt_html, html_transformed)

    print("XSLT Processor complete.")
    print("CSV transform saved to:", csv_transformed)
    print("HTML transform saved to:", html_transformed)

    print("\n-----------------------------------------------\n")

    

