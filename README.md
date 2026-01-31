# Care India State Data

Indian govt state and lsg data for CARE

## Features

This package provides a script to load Indian government organization data (states, districts, local bodies, and wards) into a Django application.

## Installation

Install directly from GitHub:

```bash
pip install git+https://github.com/ohcnetwork/care-india-state-data.git
```

Or install from a specific release:

```bash
pip install https://github.com/ohcnetwork/care-india-state-data/releases/download/<version>/care_india_state_data-<version>-py3-none-any.whl
```

## Usage

The package includes a standalone script that can be run to load government organization data into your Django database.

### Running the Script

```bash
python -m care_india_state_data.load_govt_organization [OPTIONS]
```

### Available Options

- `--state <state_name>`: Load data for a specific state (default: `all`)
- `--load-districts`: Load district data
- `--load-local-bodies`: Load local body data
- `--load-wards`: Load ward data
- `-v, --verbosity <0|1|2>`: Set verbosity level (0=ERROR, 1=INFO, 2=DEBUG)

### Examples

Load all states only:
```bash
python -m care_india_state_data.load_govt_organization
```

Load states and districts for all states:
```bash
python -m care_india_state_data.load_govt_organization --load-districts
```

Load complete data (states, districts, local bodies, and wards) for Kerala:
```bash
python -m care_india_state_data.load_govt_organization --state kerala --load-districts --load-local-bodies --load-wards
```

Load all data with debug logging:
```bash
python -m care_india_state_data.load_govt_organization --state all --load-districts --load-local-bodies --load-wards -v 2
```

## Credits

This package was created with [Cookiecutter](https://github.com/audreyfeldroy/cookiecutter) and the [audreyfeldroy/cookiecutter-pypackage](https://github.com/audreyfeldroy/cookiecutter-pypackage) project template.
