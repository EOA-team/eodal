"""
This scripts shows how to create a local metadata DBMS for storing satellite
data locally and make it searchable.
Creates tables in a PostgreSQL/PostGIS DBMS instance if not available yet.
Existing tables remain untouched!

Copyright (C) 2022 Lukas Valentin Graf

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from eodal.metadata.database.db_model import create_tables

if __name__ == '__main__':
    create_tables()
