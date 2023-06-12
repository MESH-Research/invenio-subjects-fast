# invenio-subjects-fast

FAST subject terms for InvenioRDM

Install this extension to use the FAST faceted subject terms into your InvenioRDM instance.

## Acknowledgements

Thanks to Guillaume Viger and Northwestern University for the invenio-subjects-mesh package which provided the framework for this package and the current README text.

## Installation

From your instance directory:

    pipenv install invenio-subjects-fast

This will add it to your Pipfile.

### Versions

This repository follows [calendar versioning](https://calver.org/):

`2021.06.18` is both a valid semantic version and an indicator of the year-month corresponding to the loaded FAST terms.


## Usage

There are 2 types of users for this package. Maintainers of the package and instance administrators.

### Instance administrators

For instance administrators, after you have installed the extension as per the steps above, you will want to reload your instance's fixtures: `pipenv run invenio rdm-records fixtures` . **Note that at the time of writing, InvenioRDM has no capacity to update installed fixtures without either recreating the database with `invenio-cli services setup --force` or manually updating the database. It is hoped that this situation will be fixed before the next update is made to this package. Be aware, though, that once installed this vocabulary cannot easily be updated at the moment.**

### Maintainers

The FAST vocabulary is updated every 6 months. When a new version of the FAST terms is released, this package should be updated. To do so, you can

1. Download the marcxml source files from the FAST project by running

    pipenv run invenio-subjects-fast download

2. Convert the raw terms to a set of .yaml files that InvenioRDM can use and saves them in `invenio_subjects_fast/vocabularies/` folder by running

    pipenv run invenio-subjects-fast convert

3. Bump the version number in `invenio_subjects_mesh/__init__.py` to the current date and release the updated package.
