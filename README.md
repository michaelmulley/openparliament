A site that scrapes and republishes information on Canada's House of Commons.

License
=======

Code is released under the AGPLv3 (see below). However, any site you create
using this code cannot use the openparliament.ca name or logo, except as
acknowledgement.

Copyright (C) Michael Mulley (michaelmulley.com)

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

Usage
============

This is the source code for a specific site and isn't adapted for reuse or
other purposes. But if it's useful to you, that's great!

The application runs on a recent version of Python (3.12 as of this writing).
Your best bet to get an environment running is probably Docker. A sample
docker-compose.yml is provided in the config-examples directory; copy it into the
same directory as this file and run `docker compose up`.

The app uses the Django framework, which can work with a variety of databases
(including sqlite if you don't want to run a database server), but it's only been
tested with PostgreSQL. You can download a dump of all our Parliamentary data to
load into Postgres from <https://openparliament.ca/data-download/>.
