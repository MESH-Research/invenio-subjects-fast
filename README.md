# invenio-subjects-fast

FAST subject vocabulary for the InvenioRDM repository system.

Install this extension to use the FAST (Faceted Application of Subject
Terminology) subject vocabulary in your InvenioRDM instance. FAST is developed
by OCLC Research (https://www.oclc.org/research/areas/data-science/fast.html)
and adapts the Library of Congress Subject Headings to use a faceted structure,
allowing flexible and efficient tagging and searching. FAST is made available
under the Open Data Commons Attribution License
(https://www.oclc.org/research/areas/data-science/fast/odcby.html).

Some of the facets in FAST are extremely large. (Well over a million terms.) So
this package provides the nine facets of the FAST vocabulary in Invenio as nine
separate subject vocabularies. Each term's id is the full URL for the term
(e.g., http://id.worldcat.org/fast/1204165).

The invenio-subjects-fast package comes with a preconfigured set of jsonl files
ready to be loaded as fixtures into InvenioRDM. It also includes scripts to
download the raw .marcxml files from the FAST project and convert them into
jsonl vocabulary files. This download and conversion process will only be
necessary, though, when the FAST terms are updated.

## Installation

From your InvenioRDM instance directory:

```bash
pip install invenio-subjects-fast
```

Or, if the instance uses uv:

```bash
uv add invenio-subjects-fast
```

## Usage

The package will automatically provide the entry points for InvenioRDM to
register the vocabulary as a subject scheme. If you are installing the
vocabulary in an existing InvenioRDM instance, though, you will have to tell
Invenio to create vocabulary fixtures from the package files:

```bash
uv run invenio rdm-records fixtures
```

**Note that this fixture creation will take quite a few minutes**, and on
lower-powered processors may take more than half an hour. During this time the
terminal process will simply read "Creating required fixtures..." This should
eventually be followed by "Created required fixtures!" But the initial loading
process for such a large set of vocabulary files is very slow.

**The vocabulary terms will not be available for some time** even after the
fixtures have been created and you receive the "Created required fixtures!"
message. This is because the indexing of each vocabulary term is delegated to a
RabbitMQ task to be performed in due course by a celery worker. It **may take as
long as several hours** for celery to complete all of these queued tasks. Once
the queue has completed, though, the FAST terms will appear as suggestions in
the subject field of the deposit form.

## Vocabulary file format

The official InvenioRDM documentation recommends yaml files for custom
vocabularies. This file format is quite slow, though, for InvenioRDM to ingest.
So this module instead provides jsonl formatted files.

## Updating the vocabulary

The invenio-subjects-fast package includes a preconfigured set of Invenio
vocabulary files in jsonl format. You can, however, download and compile updated
FAST source files for yourself.

**As of 23 July 2026**, automated downloads from the OCLC ResearchWorks URL are
blocked (Cloudflare returns HTTP 403 to non-browser clients). Obtain the facet
zip files manually from
https://www.oclc.org/research/areas/data-science/fast/download.html and place
the extracted `.marcxml` files (or the downloaded `.marcxml.zip` archives, then
unzip them) in this package's `invenio_subjects_fast/downloads/` folder.

The `download` CLI may still work if OCLC lifts that restriction:

```bash
uv run invenio-subjects-fast download
```

To convert the marcxml files in `downloads/` to Invenio's subject jsonl format,
run

```bash
uv run invenio-subjects-fast convert
```

Both `download` and `convert` accept a repeatable `-f` / `--facet` option to
process only selected facets (e.g. `-f formgenre`). Omit `--facet` to process
all facets.

## Loading updated vocabularies into InvenioRDM

After installing a newer release of this package (or staging corrected jsonl
files), refresh existing subject terms with `invenio vocabularies update`.

Invenio’s stock subjects CLI defaults to a **YAML** reader. FAST data is
**JSONL**, so you must pass this package’s datastream config as `--filepath`
(shipped as `invenio_subjects_fast/vocabularies/subjects_datastream.yaml`) and
the facet file as `--origin`:

```bash
invenio vocabularies update -v subjects \
  --filepath "$(python -c 'from importlib.resources import files; print(files("invenio_subjects_fast") / "vocabularies" / "subjects_datastream.yaml")')" \
  --origin "$(python -c 'from importlib.resources import files; print(files("invenio_subjects_fast") / "vocabularies" / "subjects_fast_<facet>.jsonl")')"
```

Replace `<facet>` with the facet slug (e.g. `formgenre`, `topical`). Repeat for
each facet file you need to refresh.

If existing terms were modified (same subject `id`, changed fields such as label
or `scheme`), rebuild record indexes afterward (for example
`invenio rdm-records rebuild-index`) so denormalized subject data on records
stays consistent. See your instance's operator documentation for full steps.

## Updating this package

The FAST vocabulary is updated every 6 months. When a new version of the FAST
terms is released, this package should be updated. You can tell that an update
may be necessary if the current version of the FAST vocabulary was released
after the date used as the version number for this package.

If you would like to contribute an updated version, first create a fork of the
(https://github.com/MESH-Research/invenio-subjects-fast), clone it locally, and
install the local version of the package in development mode with uv:

```bash
uv sync
```

Then from the repository root, manually download the FAST marcxml zip files from
https://www.oclc.org/research/areas/data-science/fast/download.html into
`invenio_subjects_fast/downloads/` (see the note under
[Updating the vocabulary](#updating-the-vocabulary)), then run

```bash
uv run invenio-subjects-fast convert
```

Run the automated tests with the test-runner script:

```bash
bash run-tests.sh
```

Once the tests pass, bump the version number in
`invenio_subjects_fast/__init__.py` and in `pyproject.toml` to the current date
(YYYY.MM.DD) and submit a pull request to the main invenio-subjects-fast
repository.

### Versions

This repository follows [calendar versioning](https://calver.org/):

`2021.06.18` is both a valid semantic version and an indicator of the year-month
corresponding to the loaded FAST terms.

## Acknowledgements

Thanks to Guillaume Viger and Northwestern University for the
invenio-subjects-mesh package which provided the framework for this package and
parts of this README text.
