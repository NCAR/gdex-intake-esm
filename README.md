# gdex-intake-esm

Code used to generate the intake-esm catalogs used to access various datasets in NCAR's GDEX.

## Overview

This repository contains tools and scripts for generating intake-ESM catalogs that provide unified access to diverse Earth science datasets. While intake-ESM was originally designed for Earth System Model output, we extend its use to observations, reanalysis data, and other Earth science datasets.

## Key Features

### 1. Custom Catalog Generation Tools (ecgtools)

We use a [**custom fork of ecgtools**](https://github.com/rpconroy/ecgtools.git), Currently, pin to commit SHA = 0b3d5b5d0082812e85c821c00c2d619eed0ae3cd along with custom scripts to generate our catalogs. This allows us to:
- Handle diverse data formats and structures
- Implement custom parsing logic for different data sources
- Maintain consistency across various dataset types

### 2. Broad Dataset Support

Although intake-ESM is primarily meant for Earth System Model output, we leverage the package to generate catalogs for:
- **Observations** (satellite, in-situ, etc.)
- **Reanalysis datasets** (ERA5, JRA-3Q, etc.)
- **Model output** (CESM, CMIP, etc.)
- **Other Earth science data**

We strive to match our vocabulary (column names) with conventions used by other major data providers including:
- **DKRZ** (Deutsches Klimarechenzentrum)
- **Copernicus Climate Data Store**
- **NASA** data repositories
- **NOAA** data services

### 3. Multiple Access Methods

Our catalogs support different data access patterns through three main flavors:

#### a) POSIX
Direct filesystem access for users on NCAR HPC systems (Casper, Derecho)

#### b) HTTPS
Web-based access for remote users and standard HTTP protocols

#### c) OSDF (Open Science Data Federation)
Distributed access through the Open Science Data Federation for broader community access

## Usage Examples

For comprehensive usage examples and tutorials:

- **NCAR HPC users**: Visit [gdex-examples](https://ncar.github.io/gdex-examples/)
- **OSDF users**: Visit [osdf_examples](https://ncar.github.io/osdf_examples/)

## Support and Contributions

### Issues and Feature Requests

We welcome feedback from the community! Please use GitHub issues for:
- **Bug reports** when something is broken
- **Feature requests** for new functionality or datasets

**Note**: While we appreciate all feature requests, please understand that we may not be able to fulfill all requests due to resource constraints and project priorities.

### Getting Help

1. Check the documentation and examples linked above
2. Search existing GitHub issues for similar problems
3. Open a new issue with detailed information about your use case

## Repository Structure

```
├── README.md
├── requirements.txt
├── generator/          # Core catalog generation tools
│   ├── create_catalog.py
│   └── modify_catalog.py
├── notebooks/          # Example notebooks and development work
└── test/              # Test scripts
```

## Installation

```bash
git clone https://github.com/NCAR/gdex-intake-esm.git
cd gdex-intake-esm
pip install -r requirements.txt
```
