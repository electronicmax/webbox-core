#    This file is part of WebBox.
#
#    Copyright 2011-2012 Daniel Alexander Smith
#    Copyright 2011-2012 University of Southampton
#
#    WebBox is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    WebBox is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with WebBox.  If not, see <http://www.gnu.org/licenses/>.

import logging

class ObjectStore:
    """ Stores objects in a database, handling import, export and versioning. """

    def __init__(self, conn):
        """
            conn is a postgresql psycopg2 database connection
        """
        self.conn = conn

        # TODO FIXME determine if autocommit has to be off for PL/pgsql support
        self.conn.autocommit = True

    def get_latest(self, uri):
        """ Get the latest version of an object, as expanded JSON-LD notation.
            uri of the object
        """
        
        cur = self.conn.cursor()

        cur.execute("SELECT version, predicate, object_order, obj_type, obj_value, obj_lang, obj_datatype FROM wb_v_latest_triples WHERE subject = %s ORDER BY predicate, object_order", [uri])
        rows = cur.fetchall()

        obj_out = {}
        for row in rows:
            (latest_version, predicate, obj_order, obj_type, obj_value, obj_lang, obj_datatype) = row
            if predicate not in obj_out:
                obj_out[predicate] = []

            if "@version" not in obj_out:
                obj_out["@version"] = latest_version

            if obj_type == "resource":
                obj_key = "@id"
            elif obj_type == "literal":
                obj_key = "@value"
            else:
                raise Exception("Unknown object type from database {0}".format(obj_type)) # TODO create a custom exception to throw

            obj_struct = {}
            obj_struct[obj_key] = obj_value

            if obj_lang is not None:
                obj_struct["@language"] = obj_lang

            if obj_datatype is not None:
                obj_struct["@type"] = obj_datatype


            obj_out[predicate].append(obj_struct)
    
        cur.close()
        return obj_out


    def add(self, graph_uri, objs, specified_prev_version):
        """ Add new objects, or new versions of objects, to a graph in the database.

            graph_uri of the named graph,
            objs, json expanded notation of objects in the graph,
            specified_prev_version of the named graph (must match max(version) of the graph, or zero if the object doesn't exist, or the store will return a IncorrectPreviousVersionException

            returns information about the new version
        """

        # TODO FIXME XXX lock the table(s) as appropriate inside a transaction (PL/pgspl?) here

        cur = self.conn.cursor()

        cur.execute("SELECT latest_version FROM wb_v_latest_graphvers WHERE graph_uri = %s", [graph_uri])
        row = cur.fetchone()

        if row is None:
            actual_prev_version = 0
        else:
            actual_prev_version = row[0]

        if actual_prev_version != specified_prev_version:
            raise IncorrectPreviousVersionException("Actual previous version is {0}, specified previous version is: {1}".format(actual_prev_version, specified_prev_version))

        new_version = actual_prev_version + 1

        self.add_graph_version(graph_uri, objs, new_version)

        cur.close()
        return {"@version": new_version, "@graph": graph_uri}


    def get_string_id(self, string):
        """ Get the foreign key ID of a string from the wb_strings table. Create one if necessary. """
        cur = self.conn.cursor()

        # FIXME write a PL/pgsql function for this with table locking
        cur.execute("SELECT wb_strings.id_string FROM wb_strings WHERE wb_strings.string = %s", [string])
        existing_id = cur.fetchone()

        if existing_id is None:
            cur.execute("INSERT INTO wb_strings (string) VALUES (%s) RETURNING id_string", [string])
            existing_id = cur.fetchone()
            self.conn.commit()

        cur.close()
        return existing_id

    def get_object_id(self, type, value, language, datatype):
        """ Get the foreign key ID of an object from the wb_objects table. Create one if necessary. """
        cur = self.conn.cursor()

        # FIXME write a PL/pgsql function for this with table locking
        cur.execute("SELECT id_object FROM wb_objects WHERE obj_type = %s AND obj_value = %s AND obj_lang "+("IS" if language is None else "=")+" %s AND obj_datatype "+("IS" if language is None else "=")+" %s", [type, value, language, datatype])
        existing_id = cur.fetchone()

        if existing_id is None:
            cur.execute("INSERT INTO wb_objects (obj_type, obj_value, obj_lang, obj_datatype) VALUES (%s, %s, %s, %s) RETURNING id_object", [type, value, language, datatype])
            existing_id = cur.fetchone()
            self.conn.commit()

        cur.close()
        return existing_id


    def get_triple_id(self, subject, predicate, object):
        """ Get the foreign key ID of a triple from the wb_triples table. Create one if necessary. """
        cur = self.conn.cursor()

        # FIXME write a PL/pgsql function for this with table locking
        cur.execute("SELECT id_triple FROM wb_triples WHERE subject = %s AND predicate = %s AND object = %s", [subject, predicate, object])
        existing_id = cur.fetchone()

        if existing_id is None:
            cur.execute("INSERT INTO wb_triples (subject, predicate, object) VALUES (%s, %s, %s) RETURNING id_triple", [subject, predicate, object])
            existing_id = cur.fetchone()
            self.conn.commit()

        cur.close()
        return existing_id


    def add_graph_version(self, graph_uri, objs, version):
        """ Add new version of a graph.
        """

        # TODO FIXME XXX lock the table(s) as appropriate inside a transaction (PL/pgspl?) here
        cur = self.conn.cursor()

        id_graph_uri = self.get_string_id(graph_uri)

        # TODO add this
        id_user = 1

        cur.execute("INSERT INTO wb_graphvers (graph_version, graph_uri, change_user, change_timestamp) VALUES (%s, %s, %s, CURRENT_TIMESTAMP) RETURNING id_graphver", [version, id_graph_uri, id_user])
        id_graphver = cur.fetchone()

        for obj in objs:
            
            if "@id" in obj:
                uri = obj["@id"]
            else:
                raise Exception("@id required in all objects")

            id_subject = self.get_string_id(uri)

            triple_order = 0

            for predicate in obj:
                if predicate[0] == "@":
                    continue # skip over json_ld predicates

                id_predicate = self.get_string_id(predicate)

                sub_objs = obj[predicate]
                for object in sub_objs:
                    if "@value" in object:
                        type = "literal"
                        value = object["@value"]
                    elif "@id" in object:
                        type = "resource"
                        value = object["@id"]

                    language = None
                    if "@language" in object:
                        language = object["@language"]

                    datatype = None
                    if "@type" in object:
                        datatype = object["@type"]

                    id_value = self.get_string_id(value)
                    id_object = self.get_object_id(type, id_value, language, datatype)
                    
                    id_triple = self.get_triple_id(id_subject, id_predicate, id_object)

                    triple_order += 1

                    cur.execute("INSERT INTO wb_graphver_triples (graphver, triple, triple_order) VALUES (%s, %s, %s)", [id_graphver, id_triple, triple_order])

        cur.close()

class IncorrectPreviousVersionException(BaseException):
    """ The specified previous version did not match the actual previous version. """
    pass

