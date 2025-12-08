# Automation for Data Accessioner and XSLTProcessor programs, and fixity checker using hashlib in Python

## Data Accessioner
- Transfers files from disks onto a file server
- Output: XML file and the full directory from the input
- How the function works:
    - Recursively copies or moves files from the input directory
    - Preserves the original file timestamps
    - Generates an XML report
    - Recreates the full directory structure from the input directory

## XSLT Processor
- Parses the report from Data Accessioner
- Output: CSV and HTML reports
- How the function works:
    - Transfroms the XML report from previous function into a CSV and HTML report

## Hashlib function
- Parses the report from Data Accessioner, creates a list of files and their checksums, then validates those checksums with the checksums on the disk
- Output: CSV and log report
- How the function works:
    - Recomputes MD5 checksums for all of the files in the input directory
    - Compares original checksum to stored checksum
    - Flags MISSING, MISMATCH, or ERROR (OK if they match)

## This project <u>mimics</u> these 3 programs for automation.
