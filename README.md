# nebula
A toolkit for [Project Electron](http://projectelectron.rockarch.org/) microservices, built with Django 2.0/MySQL/Python 3.6.

## What's here

- `.travis.yml` - Travis CI configuration (useful when you push code to GitHub)
- `Dockerfile` - Docker container configuration
- `docker-compose.yml` - Docker Compose configuration
- `entrypoint.sh` - A script which runs after the container starts up. If you want to add default objects or users, this is a good place to do it.
- `requirements.txt` - Python package requirements
- `wait-for-it.sh` - Makes the Django server wait until the MySQL service is up before attempting to start.

## Requirements

Using this repo requires having [Docker](https://store.docker.com/search?type=edition&offering=community) installed.

## Getting started

Clone the repository to a new directory:

    $ git clone git@github.com:helrond/nebula.git new_project

Move to the root directory of the repository:

    cd new_project/

Create a new Django project by running `django-admin.py` in the Docker container, replacing "new_project" with the name of the new service you are building:

    docker-compose run web django-admin.py startproject new_project .

Uncomment the `entrypoint` key in `docker-compose.yml`, and still in the root directory, run docker-compose:

    $ docker-compose up

Once the application starts successfully, you should be able to access it in your browser at `http://localhost:8000`

When you're done, shut down docker-compose:

    $ docker-compose down

Before pushing code, remember to change your remotes!

## License

Code is released under an MIT License, as all your code should be. See [LICENSE](LICENSE) for details.
