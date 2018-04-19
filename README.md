# fornax

A microservice to create Archivematica-compliant Submission Information Packages (SIPs)

[![Build Status](https://travis-ci.org/RockefellerArchiveCenter/fornax.svg?branch=master)](https://travis-ci.org/RockefellerArchiveCenter/fornax)

## Assumptions

Fornax currently makes the following assumptions:
- The files for incoming SIPs will have passed through Aurora, and therefore will:
  - be structured as valid bags
  - not contain viruses
  - contain at least the minimum metadata elements in `bag-info.txt` as defined in the source organization's BagIt Profile
- All bags will have a unique name, and that name will be reflected in the `machine_file_name` field of JSON responses available from Aurora's `transfers` endpoint.
- All bags will be moved to the `UPLOAD_DIR` defined in `fornax/settings.py`.

## Setup

Clone the repository

    $ git clone git@github.com:RockefellerArchiveCenter/fornax.git

Install [Docker](https://store.docker.com/search?type=edition&offering=community) (trust me, it makes things a lot easier)

Run docker-compose from the root directory

    $ cd fornax
    $ docker-compose up

Once the application starts successfully, you should be able to access the application in your browser at `http://localhost:8000`

When you're done, shut down docker-compose

    $ docker-compose down


### Data Persistence

Right now, the Docker container does not persist any data, which means that when you shut down the services using `docker-compose down`, you'll lose any data you entered. In order to facilitate development, a few default objects will be created for you when you run `docker-compose up`.


#### Users

By default a new superuser is created. See `entrypoint.sh` for those users and associated credentials. THIS IS FOR TESTING PURPOSES ONLY, BE SURE TO CHANGE THIS IN PRODUCTION.


## Usage

| Method | URL | Parameters | Response  | Behavior  |
|--------|-----|---|---|---|
|GET|/sips| |200|Returns a list of SIPs|
|GET|/sips/{id}| |200|Returns data about an individual SIP|
|POST|/sips||200|Starts the process of creating an Archivematica-compliant SIP from an transfer in Aurora. |
|GET|/status||200|Return the status of the microservice


### Authentication

In progress

### Creating SIPs

In progress

## Logging

Fornax uses `structlog` to output structured JSON logs. Logging can be configured in `settings.py`.


## License

MIT License, obvs. See [LICENSE](LICENSE) for details.
