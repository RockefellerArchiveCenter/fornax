# fornax

A microservice to create Archivematica-compliant Submission Information Packages (SIPs)

[![Build Status](https://travis-ci.org/RockefellerArchiveCenter/fornax.svg?branch=master)](https://travis-ci.org/RockefellerArchiveCenter/fornax)

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

SIPs will be created when a POST request is sent to the `sips` endpoint.

SIPs are assembled on a regular basis when the `AssembleSIPs` cron job is run. If the files for a SIP do not exist (or are in the process of being transferred) assembly is skipped for that SIP until the next time the routine is run.

SIP Assembly consists of the following steps (the `SIPAssembler` class):
- Moving the SIP to the processing directory (SIPS are validated before and after moving)
- Restructuring the SIP for Archivematica compliance by:
  - Moving objects in the `data` directory to `data/objects`
  - Adding an empty 'logs' directory
  - Adding a `metadata` directory containing a `submissionDocumentation` subdirectory
- Creating `rights.csv` and adding it to the `metadata` directory
- Creating submission documentation and adding to the `metadata/submissionDocumentation` subdirectory
- Adding a URI to `bag-info.txt` using the `Internal-Sender-Identifier` field
- Updating bag manifests to account for restructuring and changes to files
- Delivering the SIP to the Archivematica Transfer Source (SIPS are validated before and after moving)

![SIP Assembly diagram](sip_assembly.png)

### Assumptions

Fornax currently makes the following assumptions:
- The files for incoming SIPs will have passed through Aurora, and therefore will:
  - be structured as valid bags
  - be virus-free
  - contain at least the minimum metadata elements in `bag-info.txt` as defined in the source organization's BagIt Profile
- All bags will have a unique name, and that name will be reflected in the `machine_file_name` field of JSON responses available from Aurora's `transfers` endpoint.
- All bags will be moved to the `UPLOAD_DIR` defined in `fornax/settings.py` by some means (FTP, rsync, HTTP). Fornax doesn't care how or when they get there, it will just handle them when they arrive.
- For an example of the data Fornax expects from Aurora (both bags and JSON), see the `fixtures/` directory.


### Routes

| Method | URL | Parameters | Response  | Behavior  |
|--------|-----|---|---|---|
|GET|/sips| |200|Returns a list of SIPs|
|GET|/sips/{id}| |200|Returns data about an individual SIP|
|POST|/sips||200|Creates a SIP object from an transfer in Aurora. |
|GET|/status||200|Return the status of the microservice


### Authentication

This application uses [JSON Web Token Authentication](). In order to get a token, you must POST a valid username and password to the `/get-token/` endpoint:

    curl http://localhost:8000/get-token/ -d username=user&password=pass123

The response will contain a token

    { 'token' : '9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b' }

This token key should be included in the `Authorization` header of your requests, prefixed by the string "JWT" followed by whitespace.

    Authorization: JWT 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b

### Creating SIPs

SIPs will be created when a POST request is sent to the `sips` endpoint. SIPs are assembled on a regular basis when the `AssembleSIPs` cron job is run. If the files for a SIP do not exist (or are in the process of being transferred) assembly is skipped for that SIP.

SIP Assembly consists of the following steps (the `SIPAssembler` class):
- Moving the SIP to the processing directory (SIPS are validated before and after moving)
- Restructuring the SIP for Archivematica compliance by:
  - Moving objects in the `data` directory to `data/objects`
  - Adding an empty 'logs' directory
  - Adding a `metadata` directory containing a `submissionDocumentation` subdirectory
- Creating `rights.csv` and adding it to the `metadata` directory
- Creating submission documentation and adding to the `metadata/submissionDocumentation` subdirectory
- Adding a URI to `bag-info.txt` using the `Internal-Sender-Identifier` field
- Updating bag manifests to account for restructuring and changes to files
- Delivering the SIP to the Archivematica Transfer Source (SIPS are validated before and after moving)


## Logging

Fornax uses `structlog` to output structured JSON logs. Logging can be configured in `fornax/settings.py`.


## License

MIT License, obvs. See [LICENSE](LICENSE) for details.
