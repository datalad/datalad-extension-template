# DataLad PublicnEUro extension

This repository contains a datalad extension that simplifies data download
from PublicnEUro collections.


# Installation

Install the extension via pip (a virtual environment is recommended):

```bash
> pip install datalad-publicneuro
```

# Usage
The extension provides the new git annex special remote `uncurl-publicneuro`. To use it, activate the special remote in your DataLad dataset:

```bash
git annex initremote uncurl-publicneuro type=external externaltype=uncurl-publicneuro encryption=none
```

The `uncurl-publicneuro` special remote handles URLs with the following structure (where `<dataset-id>` is the PublicnEUro ID of the dataset, e.g., `PN000001`, and `path` is the absolute path of a file within the dataset, e.g., `/README.txt`):

```
publicneuro+https://<dataset-id><path>
```

The following command adds a reference to a file in a PublicnEUro dataset and downloads the file content (here the file `/README.txt` of dataset `PN000001` is added with the local name `README.txt`):

```bash
> git annex addurl --file README.txt publicneuro+https://PN000001/README.txt
```

The command will prompt for credentials if no credential are available yet. After successful authentication, the file will be downloaded and added to the annex.
Valid credentials will be stored in DataLad's credential store and automatically used for subsequent `addurl`-commands.


# Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) if you are interested in internals or
contributing to the project.
