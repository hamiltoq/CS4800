# Automation for Data Accessioner, XSLTProcessor, and DAFixity

## Data Accessioner
- Transfers files from disks onto a file server
- Output: XML file

## XSLT Processor
- Parses the report from Data Accessioner
- Output: CSV and HTML reports

## DAFixity
- Parses the report from Data Accessioner, creates a list of files and their checksums, then validates those checksums with the checksums on the disk
- Output: CSV report
