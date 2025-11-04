---
title: Introduction
date: 2025-11-04
authors:
  - name: Chia-Wei Hsu
    affiliations:
    - NCAR|NSF
---

# Introduction

Welcome to the **GDEX Intake ESM Catalog** documentation! This project provides tools and scripts for generating intake-ESM catalogs that enable unified access to diverse Earth science datasets within NCAR's GDEX infrastructure.

:::{warning} Important Notice
This documentation is under active development and is intended primarily for internal use by the GDEX team. It is being prepared to align with open‑science and open‑data principles, promoting transparency and reproducibility of the data‑processing pipeline.
:::

## What is GDEX Intake ESM?

While intake-ESM was originally designed for Earth System Model output, we extend its capabilities to support a broader range of Earth science data including:

- **Observations** (satellite, in-situ measurements)
- **Reanalysis datasets** (ERA5, JRA-3Q, etc.)
- **Model output** (CESM, CMIP, etc.)
- **Other Earth science datasets**

## Key Features

### 🛠️ Custom Catalog Generation
Our primary tool `generator/create_catalog.py` creates intake-ESM catalogs for any dataset directory with flexible configuration options for different data formats and structures.

### 🌐 Multiple Access Methods
Generated catalogs support three access patterns :
- **POSIX**: Direct filesystem access for NCAR HPC users
- **HTTPS**: Web-based access for remote users
- **OSDF**: Distributed access through Open Science Data Federation

### 📊 Broad Dataset Support
Compatible with diverse data formats including NetCDF, Zarr, and Kerchunk reference files, following vocabulary conventions used by major data providers (DKRZ, Copernicus, NASA, NOAA).

## Quick Start

Generate a basic catalog:
```bash
python generator/create_catalog.py /path/to/data \
    --out /output/directory \
    --catalog_name my_catalog \
    --description "My dataset catalog"
```

For comprehensive usage examples:
- **NCAR HPC users**: [gdex-examples](https://ncar.github.io/gdex-examples/)
- **OSDF users**: [osdf_examples](https://ncar.github.io/osdf_examples/)

## Repository Structure

- **`generator/`** - Core catalog generation tools
- **`notebooks/`** - Example Jupyter notebooks demonstrating usage 
- **`examples/`** - Python script examples for generating dataset catalog
- **`test/`** - Test scripts and validation tools

## Content

This documentation provides:
1. Understanding the catalog generation process
2. Accessing generated catalogs through different methods
