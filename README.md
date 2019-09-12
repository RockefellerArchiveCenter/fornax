# fornax

A microservice to create Archivematica-compliant Submission Information Packages (SIPs).

fornax is part of [Project Electron](https://github.com/RockefellerArchiveCenter/project_electron), an initiative to build sustainable, open and user-centered infrastructure for the archival management of digital records at the [Rockefeller Archive Center](http://rockarch.org/).

[![Build Status](https://travis-ci.org/RockefellerArchiveCenter/fornax.svg?branch=master)](https://travis-ci.org/RockefellerArchiveCenter/fornax)

## Setup

Install [git](https://git-scm.com/) and clone the repository

    $ git clone git@github.com:RockefellerArchiveCenter/fornax.git

Install [Docker](https://store.docker.com/search?type=edition&offering=community) and run docker-compose from the root directory

    $ cd fornax
    $ docker-compose up

Once the application starts successfully, you should be able to access the application in your browser at `http://localhost:8003`

When you're done, shut down docker-compose

    $ docker-compose down

Or, if you want to remove all data

    $ docker-compose down -v

### Configuration

You will need to edit configuration values in `fornax/config.py` to point to your instance of Archivematica.

## Services

fornax has six services, all of which are exposed via HTTP endpoints (see [Routes](#routes) section below):

* Store SIPs - Creates a SIP object.
* SIP Assembly - This is the main service for this application, and consists of the following steps:
  * Moving the SIP to the processing directory (SIPS are validated before and after moving).
  * Restructuring the SIP for Archivematica compliance by:
    * Moving objects in the `data` directory to `data/objects`.
    * Adding an empty `logs` directory.
    * Adding a `metadata` directory containing a `submissionDocumentation` subdirectory.
  * Creating `rights.csv` and adding it to the `metadata` directory.
  * Creating submission documentation and adding to the `metadata/submissionDocumentation` subdirectory.
  * Adding an identifier to `bag-info.txt` using the `Internal-Sender-Identifier` field.
  * Adding a `processingMCP.xml` file which sets processing configurations for Archivematica.
  * Updating bag manifests to account for restructuring and changes to files.
  * Delivering the SIP to the Archivematica Transfer Source (SIPS are validated before and after moving).
* Start Transfer - starts a transfer in Archivematica.
* Approve Transfer - approves a transfer in Archivematica.
* Cleanup - removes files from the destination directory.
* Request Cleanup - sends a POST request to another service requesting cleanup of the source directory. fornax only has read access for this directory.

  ![SIP Assembly diagram](fornax-services.png)

For an example of the data fornax expects to receive (both bags and JSON), see the `fixtures/` directory


### Routes

| Method | URL | Parameters | Response  | Behavior  |
|--------|-----|---|---|---|
|GET|/sips| |200|Returns a list of SIPs|
|GET|/sips/{id}| |200|Returns data about an individual SIP|
|POST|/sips||200|Creates a SIP object from an transfer in Aurora.|
|POST|/assemble||200|Runs the SIPAssembly routine.|
|POST|/start||200|Starts the next transfer in Archivematica.|
|POST|/approve||200|Approves the next transfer in Archivematica.|
|POST|/cleanup||200|Removes files from destination directory.|
|POST|/request-cleanup||200|Notifies another service that processing is complete.|
|GET|/status||200|Return the status of the microservice|
|GET|/schema.json||200|Returns the OpenAPI schema for this application|


## License

This code is released under an [MIT License](LICENSE).
