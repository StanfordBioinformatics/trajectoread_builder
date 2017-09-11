# trajectoread builder

## Overview
Builder is a module of the trajectoread suite of tools 
designed to simplify deployment of applets and workflows on DNAnexus.
It is a command-line tool that allows users to automatically build DNAnexus 
workflows based on JSON configuration files.

## Functions

* Use JSON file to manage DNAnexus build environments
* Use JSON files to codify workflow configurations
* Build workflows
* Build applets

## Value

* Build workflows automatically
* Simplify new applet & workflow deployment
* Reduce deployment errors

## Files
* **builder.py**: Python script used to build applets and workflows.
* **builder.json**: Configuration file with user-specific information describing 
DNAnexus build locations.
* **workflows/fastqc_bwa-mem_gatk-genotyper.json**: Sample configuration file used to generate a 3-step workflow.

## Getting Started

This will guide you through the steps of installing builder, configuring the JSON file, and building a sample applet & workflow on DNAnexus.

### 1. Install the DNAnexus SDK
Visit https://wiki.dnanexus.com/Downloads and follow instructions to 
install dx-toolkit.

### 2. Clone the repository.

```
git clone git@github.com:StanfordBioinformatics/trjread-builder.git
```

### 3. Rename builder.json.template file.

```r
mv builder.json.template builder.json
```

### 4. Populatate builder.json configuration data
Open builder.json file in a text editor and fill in DNAnexus environment information.

### 5. Build FastQC applet on DNAnexus

```r
python builder.py -e develop -r aws:us-east-1 -a fastqc
```

### 6. Build sample workflow on DNAnexus

```r
python builder.py -e develop -r aws:us-east-1 -w workflows/fastqc_bwa-mem_gatk-genotyper.json
```
