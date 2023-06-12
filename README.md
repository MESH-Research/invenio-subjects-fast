# invenio-subjects-fast

FAST subject vocabulary for the InvenioRDM repository system.

Install this extension to use the FAST (Faceted Application of Subject Terminology) subject vocabulary in your InvenioRDM instance. FAST is developed by OCLC Research (https://www.oclc.org/research/areas/data-science/fast.html) and adapts the Library of Congress Subject Headings to use a faceted structure, allowing flexible and efficient tagging and searching. FAST is made available under the Open Data Commons Attribution License (https://www.oclc.org/research/areas/data-science/fast/odcby.html).

Some of the facets in FAST are extremely large. So this package provides the nine facets of the FAST vocabulary in Invenio as nine separate subject vocabularies. Each term includes the id number and the human readable (English) label, separated by a colon.

## Installation

The invenio-subjects-fast package comes with a preconfigured set of
From your instance directory:

    pipenv install invenio-subjects-fast

This will add the package to your Pipfile and install it in your InvenioRDM instance's virtual environment.

## Usage

The package will automatically provide the entry points for InvenioRDM to register the vocabulary as a subject scheme. If you are installing the vocabulary in an existing InvenioRDM instance, though, you will have to tell Invenio to create vocabulary fixtures from the package files:

    pipenv run invenio rdm-records fixtures

**Note that this indexing will take several minutes**, during which time the terminal process will simply read "Creating required fixtures..." This should eventually be followed by "Created required fixtures!" But the indexing process for such a large set of vocabulary files is very slow.

## Updating the vocabulary

The invenio-subjects-fast package includes a preconfigured set of Invenio vocabulary files in yaml format. You can, however, download and compile updated FAST source files for yourself. First, from your Invenio instance directory, run

    pipenv run invenio-subjects-fast download

This will download the nine separate vocabulary facets from the FAST project's download page as marcxml files (https://www.oclc.org/research/areas/data-science/fast/download.html).

To convert these to Invenio's subject yaml format, run

    pipenv run invenio-subjects-fast convert


## Issues with loading updated vocabularies into InvenioRDM

**Note that at the time of writing, InvenioRDM has no capacity to update installed fixtures without either recreating the database with `invenio-cli services setup --force` or manually updating the database. It is hoped that this situation will be fixed before the next update is made to this package. Be aware, though, that once installed this vocabulary cannot easily be updated at the moment.**


## Updating this package


The FAST vocabulary is updated every 6 months. When a new version of the FAST terms is released, this package should be updated. You can tell that an update may be necessary if the current version of the FAST vocabulary was released after the date used as the version number for this package.

If you would like to contribute an updated version, first create a fork of the (https://github.com/MESH-Research/invenio-subjects-fast), clone it locally, and install the local version of the package in development mode. Then from the folder where the invenio-subjects-fast package was installed, run

    pipenv run invenio-subjects-fast download

followed by

    pipenv run invenio-subjects-fast convert

Run the automated tests with the test-runner script:

    bash run-tests.sh

Once the tests pass, bump the version number in `invenio_subjects_mesh/__init__.py` and in `pyproject.toml` to the current date (YYYY-MM-DD) and submit a pull request to the main invenio-subjects-fast repository.


### Versions

This repository follows [calendar versioning](https://calver.org/):

`2021.06.18` is both a valid semantic version and an indicator of the year-month corresponding to the loaded FAST terms.


## Acknowledgements

Thanks to Guillaume Viger and Northwestern University for the invenio-subjects-mesh package which provided the framework for this package and the current README text.
